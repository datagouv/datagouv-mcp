import csv
import gzip
import io
import json
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client

logger = logging.getLogger("datagouv_mcp")


def register_download_and_parse_resource_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def download_and_parse_resource(
        resource_id: str,
        max_rows: int = 20,
        max_size_mb: int = 500,
    ) -> str:
        """
        Download and parse a resource directly (bypasses Tabular API).

        Use for JSON/JSONL files, or when full dataset analysis is needed.
        Supports CSV, CSV.GZ, JSON, JSONL.

        Strategy: Start with default max_rows (20) to preview structure and size.
        If you need all data, call again with a higher max_rows value.
        For CSV/XLSX preview, prefer query_resource_data (faster).
        """
        try:
            # Get full resource data to find URL and metadata
            resource_data = await datagouv_api_client.get_resource_details(resource_id)
            resource = resource_data.get("resource", {})
            if not resource.get("id"):
                return f"Error: Resource with ID '{resource_id}' not found."

            resource_url = resource.get("url")
            if not resource_url:
                return f"Error: Resource {resource_id} has no download URL."

            resource_title = resource.get("title") or resource.get("name") or "Unknown"

            content_parts = [
                f"Downloading and parsing resource: {resource_title}",
                f"Resource ID: {resource_id}",
                f"URL: {resource_url}",
                "",
            ]

            # Download the file
            try:
                max_size = max_size_mb * 1024 * 1024
                content, filename, content_type = await _download_resource(
                    resource_url, max_size
                )
                file_size = len(content)
                content_parts.append(f"Downloaded: {file_size / (1024 * 1024):.2f} MB")
            except ValueError as e:
                return f"Error: {str(e)}"
            except Exception as e:  # noqa: BLE001
                return f"Error downloading resource: {str(e)}"

            # Detect format
            is_gzipped = filename.lower().endswith(".gz") or (
                content_type and "gzip" in content_type
            )
            file_format = _detect_file_format(filename, content_type)

            if file_format == "unknown":
                content_parts.append("")
                content_parts.append(
                    f"⚠️  Unknown file format. Filename: {filename}, "
                    f"Content-Type: {content_type}"
                )
                content_parts.append(
                    "Supported formats: CSV, CSV.GZ, JSON, JSONL, XLSX"
                )
                return "\n".join(content_parts)

            # Parse according to format
            rows = []
            try:
                if file_format == "csv" or (
                    file_format == "gzip" and "csv" in filename.lower()
                ):
                    content_parts.append("Format: CSV")
                    rows = _parse_csv(content, is_gzipped=bool(is_gzipped))
                elif file_format == "json" or file_format == "jsonl":
                    content_parts.append("Format: JSON/JSONL")
                    rows = _parse_json(content, is_gzipped=bool(is_gzipped))
                elif file_format == "xlsx":
                    content_parts.append("Format: XLSX")
                    content_parts.append(
                        "⚠️  XLSX parsing requires openpyxl library. "
                        "Please install it or use Tabular API for smaller files."
                    )
                    return "\n".join(content_parts)
                elif file_format == "xls":
                    content_parts.append("Format: XLS")
                    content_parts.append(
                        "⚠️  XLS format not supported. "
                        "Please use Tabular API or convert to XLSX/CSV."
                    )
                    return "\n".join(content_parts)
                elif file_format == "xml":
                    content_parts.append("Format: XML")
                    content_parts.append("⚠️  XML parsing not yet implemented.")
                    return "\n".join(content_parts)
                else:
                    content_parts.append(f"Format: {file_format}")
                    content_parts.append("⚠️  Format not supported for parsing.")
                    return "\n".join(content_parts)

            except Exception as e:  # noqa: BLE001
                return f"Error parsing file: {str(e)}"

            if not rows:
                content_parts.append("")
                content_parts.append("⚠️  No data rows found in file.")
                return "\n".join(content_parts)

            # Limit rows
            total_rows = len(rows)
            rows = rows[:max_rows]

            content_parts.append("")
            content_parts.append(f"Total rows in file: {total_rows}")
            content_parts.append(f"Returning: {len(rows)} row(s)")

            # Show column names
            if rows:
                columns = [str(k) if k is not None else "" for k in rows[0].keys()]
                content_parts.append(f"Columns: {', '.join(columns)}")

            # Show all parsed data (up to max_rows)
            content_parts.append("")
            if len(rows) == 1:
                content_parts.append("Data (1 row):")
            else:
                content_parts.append(f"Data ({len(rows)} rows):")
            for i, row in enumerate(rows, 1):
                content_parts.append(f"  Row {i}:")
                for key, value in row.items():
                    val_str = str(value) if value is not None else ""
                    if len(val_str) > 100:
                        val_str = val_str[:100] + "..."
                    content_parts.append(f"    {key}: {val_str}")

            if total_rows > max_rows:
                content_parts.append("")
                content_parts.append(
                    f"⚠️  Note: File contains {total_rows} rows, "
                    f"only showing first {max_rows}. "
                    "Increase max_rows parameter to see more."
                )

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error in download_and_parse_resource")
            return f"Error: {str(e)}"


async def _download_resource(
    resource_url: str, max_size: int = 500 * 1024 * 1024
) -> tuple[bytes, str, str | None]:
    """
    Download a resource with size limit.

    Returns:
        (content, filename, content_type)
    """
    async with httpx.AsyncClient() as session:
        resp = await session.get(resource_url, timeout=300.0)
        resp.raise_for_status()

        # Check content length if available
        content_length = resp.headers.get("Content-Length")
        if content_length:
            size = int(content_length)
            if size > max_size:
                raise ValueError(
                    f"File too large: {size / (1024 * 1024):.1f} MB "
                    f"(max: {max_size / (1024 * 1024):.1f} MB)"
                )

        # Download with size limit
        content = bytearray()
        async for chunk in resp.aiter_bytes(chunk_size=8192):
            content.extend(chunk)
            if len(content) > max_size:
                raise ValueError(
                    f"File too large: exceeds {max_size / (1024 * 1024):.1f} MB limit"
                )

        # Get filename from Content-Disposition or URL
        filename = "resource"
        content_disposition = resp.headers.get("Content-Disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[1].strip("\"'")
        elif "/" in resource_url:
            filename = resource_url.split("/")[-1].split("?")[0]

        content_type = resp.headers.get("Content-Type", "").split(";")[0]

        return bytes(content), filename, content_type


def _detect_file_format(filename: str, content_type: str | None) -> str:
    """Detect file format from filename and content type."""
    filename_lower = filename.lower()

    # Check by extension first
    if filename_lower.endswith(".csv") or filename_lower.endswith(".csv.gz"):
        return "csv"
    elif (
        filename_lower.endswith(".json")
        or filename_lower.endswith(".jsonl")
        or filename_lower.endswith(".ndjson")
    ):
        return "json"
    elif filename_lower.endswith(".xml"):
        return "xml"
    elif filename_lower.endswith(".xlsx"):
        return "xlsx"
    elif filename_lower.endswith(".xls"):
        return "xls"
    elif filename_lower.endswith(".gz"):
        return "gzip"
    elif filename_lower.endswith(".zip"):
        return "zip"

    # Check by content type
    if content_type:
        if "csv" in content_type:
            return "csv"
        elif "json" in content_type:
            return "json"
        elif "xml" in content_type:
            return "xml"
        elif "excel" in content_type or "spreadsheet" in content_type:
            return "xlsx"
        elif "gzip" in content_type:
            return "gzip"

    return "unknown"


def _parse_csv(content: bytes, is_gzipped: bool = False) -> list[dict[str, Any]]:
    """Parse CSV content with automatic delimiter detection."""
    if is_gzipped:
        content = gzip.decompress(content)

    try:
        text = content.decode("utf-8-sig")  # Handle BOM
    except UnicodeDecodeError:
        # Fallback to Latin-1 for French CSV files
        text = content.decode("iso-8859-1")

    # Detect delimiter automatically
    # Try to sniff the delimiter from the first few lines
    sample_lines = text.split("\n")[:5]  # Use first 5 lines for detection
    sample_text = "\n".join(sample_lines)

    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        delimiter = sniffer.sniff(sample_text, delimiters=",;\t|").delimiter
    except (csv.Error, AttributeError):
        # If sniffing fails, try common delimiters in order of likelihood
        # Count occurrences of each delimiter in the sample
        delimiter_counts = {
            ",": sample_text.count(","),
            ";": sample_text.count(";"),
            "\t": sample_text.count("\t"),
            "|": sample_text.count("|"),
        }
        # Use the delimiter with the most occurrences (but at least 2 to avoid false positives)
        if delimiter_counts:
            best_delimiter = max(delimiter_counts.items(), key=lambda x: x[1])
            if best_delimiter[1] >= 2:
                delimiter = best_delimiter[0]

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return list(reader)


def _parse_json(content: bytes, is_gzipped: bool = False) -> list[dict[str, Any]]:
    """Parse JSON content (array or JSONL)."""
    if is_gzipped:
        content = gzip.decompress(content)

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("iso-8859-1")

    # Try JSON array first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Single object, return as list
            return [data]
    except json.JSONDecodeError:
        pass

    # Try JSONL (one JSON object per line)
    lines = text.strip().split("\n")
    result = []
    for line in lines:
        if line.strip():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return result
