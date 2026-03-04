import csv
import gzip
import itertools
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client

logger = logging.getLogger("datagouv_mcp")

MAX_DOWNLOAD_SIZE_MB: int = int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "100"))
CACHE_TTL_SECONDS: int = 1800  # 30 minutes


@dataclass
class CachedFile:
    """Metadata for a file streamed to disk."""

    path: str
    filename: str
    content_type: str | None
    file_format: str  # normalised format: "csv", "jsonl", "unknown", …
    is_gzipped: bool
    created_at: float = field(default_factory=time.monotonic)

    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > CACHE_TTL_SECONDS


# In-process cache: survives across requests within the same worker.
# Key: resource_id
_file_cache: dict[str, CachedFile] = {}


def register_download_and_parse_resource_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def download_and_parse_resource(
        resource_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> str:
        """
        Download and parse a resource file in pages (fallback tool — prefer self-download).

        IMPORTANT: If your environment can fetch URLs directly (via fetch, curl, wget, or
        a browser tool), ALWAYS prefer downloading and parsing the file yourself. Use this
        tool only when you have no other way to access the file content.

        Supported formats: CSV, CSV.GZ, JSON, JSONL/NDJSON.
        For CSV/XLSX already indexed by the Tabular API, prefer query_resource_data instead
        (no download needed, supports filtering and sorting).

        Pagination:
        - Start with page=1 (default) to preview structure and get total_rows.
        - Increment page to read further chunks. Each call reuses the cached file on disk
          — the file is only downloaded once per 30-minute window.
        - page_size must be at least 1.

        Files larger than MAX_DOWNLOAD_SIZE_MB (default 100 MB) are rejected.
        JSON arrays are normalised to JSONL on first access so all subsequent pages are
        read as cheap line-based streaming (no repeated full-file parse).
        """
        page = max(page, 1)
        page_size = max(page_size, 1)

        try:
            resource_data = await datagouv_api_client.get_resource_details(resource_id)
            resource = resource_data.get("resource", {})
            if not resource.get("id"):
                return f"Error: Resource with ID '{resource_id}' not found."

            resource_url = resource.get("url")
            if not resource_url:
                return f"Error: Resource {resource_id} has no download URL."

            resource_title = resource.get("title") or resource.get("name") or "Unknown"

            content_parts = [
                f"Resource: {resource_title}",
                f"Resource ID: {resource_id}",
                f"URL: {resource_url}",
                "",
            ]

            # Retrieve or download to disk cache
            _evict_expired_cache()
            cached = _file_cache.get(resource_id)
            if cached is None or cached.is_expired():
                content_parts.append("Downloading file to local cache…")
                try:
                    max_size = MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
                    tmp_path, filename, content_type = await _stream_to_tempfile(
                        resource_url, max_size
                    )
                except ValueError as e:
                    return f"Error: {e}"
                except Exception as e:  # noqa: BLE001
                    return f"Error downloading resource: {e}"

                is_gzipped = filename.lower().endswith(".gz") or bool(
                    content_type and "gzip" in content_type
                )
                file_format = _detect_file_format(filename, content_type)

                if file_format == "unknown":
                    Path(tmp_path).unlink(missing_ok=True)
                    content_parts += [
                        "",
                        f"Unknown file format. Filename: {filename}, "
                        f"Content-Type: {content_type}",
                        "Supported formats: CSV, CSV.GZ, JSON, JSONL",
                    ]
                    return "\n".join(content_parts)

                # Normalise JSON array → JSONL so all formats use line-based streaming
                if file_format == "json":
                    try:
                        tmp_path, file_format = _normalise_json_to_jsonl(
                            tmp_path, is_gzipped
                        )
                        is_gzipped = False  # normalised file is plain text
                    except Exception as e:  # noqa: BLE001
                        Path(tmp_path).unlink(missing_ok=True)
                        return f"Error parsing JSON file: {e}"

                cached = CachedFile(
                    path=tmp_path,
                    filename=filename,
                    content_type=content_type,
                    file_format=file_format,
                    is_gzipped=is_gzipped,
                )
                _file_cache[resource_id] = cached
                file_size = Path(tmp_path).stat().st_size
                content_parts.append(
                    f"Downloaded and cached: {file_size / (1024 * 1024):.2f} MB"
                )
            else:
                content_parts.append(
                    "Using cached file (downloaded earlier this session)."
                )

            content_parts.append(f"Format: {cached.file_format.upper()}")
            content_parts.append("")

            # Parse the requested page
            try:
                rows, has_more, total_rows_hint = _read_page(
                    cached, page=page, page_size=page_size
                )
            except Exception as e:  # noqa: BLE001
                return f"Error reading page from file: {e}"

            if not rows and page == 1:
                content_parts.append("No data rows found in file.")
                return "\n".join(content_parts)

            if not rows:
                content_parts.append(
                    f"No rows on page {page}. "
                    f"Try a lower page number (last page had data)."
                )
                return "\n".join(content_parts)

            if total_rows_hint is not None:
                content_parts.append(f"Total rows in file: {total_rows_hint}")
            content_parts.append(
                f"Page {page} — {len(rows)} row(s) "
                f"(rows {(page - 1) * page_size + 1}–{(page - 1) * page_size + len(rows)})"
            )

            if rows:
                columns = [str(k) if k is not None else "" for k in rows[0].keys()]
                content_parts.append(f"Columns: {', '.join(columns)}")

            content_parts.append("")
            content_parts.append(f"Data ({len(rows)} row(s)):")
            for i, row in enumerate(rows, start=(page - 1) * page_size + 1):
                content_parts.append(f"  Row {i}:")
                for key, value in row.items():
                    val_str = str(value) if value is not None else ""
                    if len(val_str) > 200:
                        val_str = val_str[:200] + "…"
                    content_parts.append(f"    {key}: {val_str}")

            if has_more:
                content_parts += [
                    "",
                    f"More data available — call again with page={page + 1} "
                    f"(page_size={page_size}) to continue.",
                ]

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e}"
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error in download_and_parse_resource")
            return f"Error: {e}"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _evict_expired_cache() -> None:
    """Remove expired entries and delete their temp files."""
    expired = [k for k, v in _file_cache.items() if v.is_expired()]
    for key in expired:
        cached = _file_cache.pop(key)
        Path(cached.path).unlink(missing_ok=True)
        logger.debug(f"Evicted cached file for resource {key}: {cached.path}")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


async def _stream_to_tempfile(
    resource_url: str,
    max_size: int,
) -> tuple[str, str, str | None]:
    """
    Stream a remote file to a named temp file on disk.

    Returns (tmp_path, filename, content_type).
    Raises ValueError if the file exceeds max_size.
    """
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", resource_url, timeout=300.0) as resp:
            resp.raise_for_status()

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > max_size:
                raise ValueError(
                    f"File too large: {int(content_length) / (1024 * 1024):.1f} MB "
                    f"(limit: {max_size / (1024 * 1024):.0f} MB)"
                )

            content_disposition = resp.headers.get("Content-Disposition", "")
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()

            filename = "resource"
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[1].strip("\"'")
            elif "/" in resource_url:
                filename = resource_url.split("/")[-1].split("?")[0] or "resource"

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
            total = 0
            try:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > max_size:
                        tmp.close()
                        Path(tmp.name).unlink(missing_ok=True)
                        raise ValueError(
                            f"File too large: exceeds {max_size / (1024 * 1024):.0f} MB limit"
                        )
                    tmp.write(chunk)
            finally:
                tmp.close()

    return tmp.name, filename, content_type or None


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def _detect_file_format(filename: str, content_type: str | None) -> str:
    fn = filename.lower()
    if fn.endswith(".csv") or fn.endswith(".csv.gz"):
        return "csv"
    if fn.endswith(".jsonl") or fn.endswith(".ndjson") or fn.endswith(".jsonl.gz"):
        return "jsonl"
    if fn.endswith(".json") or fn.endswith(".json.gz"):
        return "json"
    if fn.endswith(".xlsx"):
        return "xlsx"
    if fn.endswith(".xls"):
        return "xls"
    if fn.endswith(".xml"):
        return "xml"
    if fn.endswith(".gz"):
        return "gzip"
    if fn.endswith(".zip"):
        return "zip"

    if content_type:
        ct = content_type.lower()
        if "csv" in ct:
            return "csv"
        if "json" in ct:
            return "json"
        if "xml" in ct:
            return "xml"
        if "excel" in ct or "spreadsheet" in ct:
            return "xlsx"
        if "gzip" in ct:
            return "gzip"

    return "unknown"


# ---------------------------------------------------------------------------
# JSON → JSONL normalisation
# ---------------------------------------------------------------------------


def _normalise_json_to_jsonl(json_path: str, is_gzipped: bool) -> tuple[str, str]:
    """
    Parse a JSON file (array or single object) and write it out as JSONL.

    Returns (new_tmp_path, "jsonl").
    The original temp file is deleted after successful conversion.
    This is the only point in the lifecycle where a JSON file is fully loaded
    into memory — it happens once and the result is cached on disk as JSONL.
    """
    opener = gzip.open if is_gzipped else open
    with opener(json_path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)

    if isinstance(data, dict):
        records: list[Any] = [data]
    elif isinstance(data, list):
        records = data
    else:
        records = [{"value": data}]

    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix="_normalised.jsonl", mode="w", encoding="utf-8"
    )
    try:
        for record in records:
            tmp.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        tmp.close()

    Path(json_path).unlink(missing_ok=True)
    return tmp.name, "jsonl"


# ---------------------------------------------------------------------------
# Paginated readers
# ---------------------------------------------------------------------------


def _read_page(
    cached: CachedFile,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool, int | None]:
    """
    Read one page from a cached file.

    Returns (rows, has_more, total_rows_hint).
    total_rows_hint is None when counting would require a full scan we haven't done.
    """
    if cached.file_format in ("csv", "jsonl"):
        return _read_line_based_page(cached, page, page_size)

    # Unsupported formats fall through with an informative error
    raise ValueError(
        f"Format '{cached.file_format}' is not supported for paginated reading. "
        "Supported: CSV, JSONL/NDJSON."
    )


def _read_line_based_page(
    cached: CachedFile,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool, int | None]:
    """Streaming page reader for CSV and JSONL."""
    offset = (page - 1) * page_size

    if cached.file_format == "csv":
        return _read_csv_page(cached.path, cached.is_gzipped, offset, page_size)
    else:
        return _read_jsonl_page(cached.path, cached.is_gzipped, offset, page_size)


def _read_csv_page(
    path: str,
    is_gzipped: bool,
    offset: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool, int | None]:
    opener = gzip.open if is_gzipped else open
    with opener(path, "rt", encoding="utf-8-sig") as fh:
        # Sniff delimiter from a small sample, then rewind
        sample = "".join(fh.readline() for _ in range(5))
        fh.seek(0)

        delimiter = ","
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except (csv.Error, AttributeError):
            counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
            best, n = max(counts.items(), key=lambda x: x[1])
            if n >= 2:
                delimiter = best

        reader = csv.DictReader(fh, delimiter=delimiter)

        # Skip rows before our page
        for _ in itertools.islice(reader, offset):
            pass

        rows = list(itertools.islice(reader, page_size))
        has_more = next(reader, None) is not None

    return rows, has_more, None


def _read_jsonl_page(
    path: str,
    is_gzipped: bool,
    offset: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], bool, int | None]:
    opener = gzip.open if is_gzipped else open
    rows: list[dict[str, Any]] = []
    has_more = False

    with opener(path, "rt", encoding="utf-8") as fh:
        line_iter = (line for line in fh if line.strip())

        # Skip rows before our page
        for _ in itertools.islice(line_iter, offset):
            pass

        for line in itertools.islice(line_iter, page_size):
            try:
                obj = json.loads(line)
                rows.append(obj if isinstance(obj, dict) else {"value": obj})
            except json.JSONDecodeError:
                continue

        has_more = next(line_iter, None) is not None

    return rows, has_more, None
