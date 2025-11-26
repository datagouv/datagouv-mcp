import csv
import gzip
import io
import json
import logging
import os
import sys
from typing import Any

import aiohttp
import uvicorn
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, tabular_api_client

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Ensure helpers loggers are also at DEBUG level
logging.getLogger("helpers.tabular_api_client").setLevel(logging.DEBUG)
logging.getLogger("helpers.datagouv_api_client").setLevel(logging.DEBUG)

mcp = FastMCP("data.gouv.fr MCP server")


@mcp.tool()
async def search_datasets(query: str, page: int = 1, page_size: int = 20) -> str:
    """
    Search for datasets on data.gouv.fr by keywords.

    Returns a list of datasets matching the search query with their metadata,
    including title, description, organization, tags, and resource count.
    Use this to discover datasets before querying their data.

    Args:
        query: Search query string (searches in title, description, tags)
        page: Page number (default: 1)
        page_size: Number of results per page (default: 20, max: 100)

    Returns:
        Formatted text with dataset information
    """
    result = await datagouv_api_client.search_datasets(
        query=query, page=page, page_size=page_size
    )

    # Format the result as text content
    datasets = result.get("data", [])
    if not datasets:
        return f"No datasets found for query: '{query}'"

    content_parts = [
        f"Found {result.get('total', len(datasets))} dataset(s) for query: '{query}'",
        f"Page {result.get('page', 1)} of results:\n",
    ]
    for i, ds in enumerate(datasets, 1):
        content_parts.append(f"{i}. {ds.get('title', 'Untitled')}")
        content_parts.append(f"   ID: {ds.get('id')}")
        if ds.get("description_short"):
            desc = ds.get("description_short", "")[:200]
            content_parts.append(f"   Description: {desc}...")
        if ds.get("organization"):
            content_parts.append(f"   Organization: {ds.get('organization')}")
        if ds.get("tags"):
            tags = ", ".join(ds.get("tags", [])[:5])
            content_parts.append(f"   Tags: {tags}")
        content_parts.append(f"   Resources: {ds.get('resources_count', 0)}")
        content_parts.append(f"   URL: {ds.get('url')}")
        content_parts.append("")

    return "\n".join(content_parts)


@mcp.tool()
async def query_dataset_data(
    question: str,
    dataset_id: str | None = None,
    dataset_query: str | None = None,
    limit_per_resource: int = 100,
) -> str:
    """
    Query data from a dataset by exploring its resources via the Tabular API.

    This tool finds a dataset (by ID or by searching), retrieves its resources, and uses
    the data.gouv.fr Tabular API to access tabular content.

    Args:
        question: The question or description of what data you're looking for
        dataset_id: Optional dataset ID if you already know which dataset to query
        dataset_query: Optional search query to find the dataset if dataset_id is not provided
        limit_per_resource: Maximum number of rows to retrieve per resource table (default: 100)

    Returns:
        Formatted text with the data found, organized by resource
    """
    try:
        # Step 1: Find the dataset
        if dataset_id:
            # Use provided dataset ID
            dataset_result = await datagouv_api_client.get_resources_for_dataset(
                dataset_id
            )
            dataset = dataset_result.get("dataset", {})
            if not dataset.get("id"):
                return f"Error: Dataset with ID '{dataset_id}' not found."
        elif dataset_query:
            # Search for dataset
            search_result = await datagouv_api_client.search_datasets(
                query=dataset_query, page=1, page_size=1
            )
            datasets = search_result.get("data", [])
            if not datasets:
                return f"Error: No dataset found for query '{dataset_query}'."
            dataset_id = datasets[0].get("id")
            dataset_result = await datagouv_api_client.get_resources_for_dataset(
                dataset_id
            )
            dataset = dataset_result.get("dataset", {})
        else:
            return (
                "Error: Either 'dataset_id' or 'dataset_query' must be provided.\n"
                "Use dataset_id if you know the exact dataset ID, or dataset_query to search for a dataset."
            )

        dataset_title = dataset.get("title", "Unknown")
        dataset_id = dataset.get("id", dataset_id)

        # Step 2: Get resources for the dataset
        resources = dataset_result.get("resources", [])
        if not resources:
            return (
                f"Dataset '{dataset_title}' (ID: {dataset_id}) has no resources.\n"
                "No data tables are available to explore."
            )

        content_parts = [
            f"Exploring dataset: {dataset_title}",
            f"Dataset ID: {dataset_id}",
            f"Question: {question}",
            f"Found {len(resources)} resource(s) to explore\n",
        ]

        # Step 3 & 4: For each resource, fetch data via the Tabular API
        found_data = False
        for resource_id, resource_title in resources:
            content_parts.append(
                f"--- Resource: {resource_title or 'Untitled'} (ID: {resource_id}) ---"
            )

            try:
                # Tabular API has a maximum page_size of 200
                page_size = max(1, min(limit_per_resource, 200))
                logger.info(
                    f"Querying Tabular API for resource: {resource_title} "
                    f"(ID: {resource_id}), page_size: {page_size}"
                )
                tabular_data = await tabular_api_client.fetch_resource_data(
                    resource_id, page=1, page_size=page_size
                )
                rows = tabular_data.get("data", [])
                meta = tabular_data.get("meta", {})
                total_count = meta.get("total")
                page_info = meta.get("page")
                page_size_meta = meta.get("page_size")

                if not rows:
                    content_parts.append(
                        "  ⚠️  No rows available (resource may be empty or filtered)."
                    )
                    content_parts.append("")
                    continue

                found_data = True
                if total_count is not None:
                    content_parts.append(f"  Total rows (Tabular API): {total_count}")
                content_parts.append(f"  Retrieved: {len(rows)} row(s)")
                if page_info is not None and page_size_meta is not None:
                    content_parts.append(
                        f"  Page info: page {page_info} (page size {page_size_meta})"
                    )

                # Show column names
                if rows:
                    columns = [str(k) if k is not None else "" for k in rows[0].keys()]
                    content_parts.append(f"  Columns: {', '.join(columns)}")

                if not rows:
                    content_parts.append("")
                    continue

                # Show sample data (first few rows)
                content_parts.append("\n  Sample data (first 3 rows):")
                for i, row in enumerate(rows[:3], 1):
                    content_parts.append(f"    Row {i}:")
                    for key, value in row.items():
                        # Truncate long values
                        val_str = str(value) if value is not None else ""
                        if len(val_str) > 100:
                            val_str = val_str[:100] + "..."
                        content_parts.append(f"      {key}: {val_str}")

                if len(rows) > 3:
                    content_parts.append(
                        f"    ... ({len(rows) - 3} more row(s) available)"
                    )

                links = tabular_data.get("links", {})
                if links.get("next"):
                    content_parts.append(
                        "  More data available via Tabular API (next page link provided)."
                    )

            except tabular_api_client.ResourceNotAvailableError as e:
                logger.warning(f"Resource not available: {resource_id} - {str(e)}")
                content_parts.append(f"  ⚠️  {str(e)}")
            except aiohttp.ClientResponseError as e:
                error_details = f"HTTP {e.status}: {e.message}"
                if hasattr(e, "request_info") and e.request_info:
                    error_details += f" - URL: {e.request_info.url}"
                logger.error(
                    f"Tabular API HTTP error for resource {resource_id}: {error_details}"
                )

                content_parts.append(f"  ❌ Tabular API error ({error_details})")
            except Exception as e:
                logger.exception(f"Unexpected error exploring resource {resource_id}")
                content_parts.append(f"  ❌ Error exploring table: {str(e)}")

            content_parts.append("")

        if not found_data:
            content_parts.append(
                "⚠️  No data tables were found or accessible for the resources in this dataset."
            )

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        return f"Error: HTTP {e.status} - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_dataset_info(dataset_id: str) -> str:
    """
    Get detailed information about a specific dataset.

    Returns comprehensive metadata including title, description, organization,
    tags, resource count, creation/update dates, and other details.

    Args:
        dataset_id: The ID of the dataset to get information about

    Returns:
        Formatted text with detailed dataset information
    """
    try:
        # Get full dataset data from API
        url = f"{datagouv_api_client.api_base_url()}1/datasets/{dataset_id}/"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 404:
                    return f"Error: Dataset with ID '{dataset_id}' not found."
                resp.raise_for_status()
                data = await resp.json()

        content_parts = [f"Dataset Information: {data.get('title', 'Unknown')}", ""]

        if data.get("id"):
            content_parts.append(f"ID: {data.get('id')}")
        if data.get("slug"):
            content_parts.append(f"Slug: {data.get('slug')}")
            content_parts.append(
                f"URL: {datagouv_api_client.frontend_base_url()}datasets/{data.get('slug')}/"
            )

        if data.get("description_short"):
            content_parts.append("")
            content_parts.append(f"Description: {data.get('description_short')}")

        if data.get("description") and data.get("description") != data.get(
            "description_short"
        ):
            content_parts.append("")
            content_parts.append(
                f"Full description: {data.get('description')[:500]}..."
            )

        if data.get("organization"):
            org = data.get("organization", {})
            if isinstance(org, dict):
                content_parts.append("")
                content_parts.append(f"Organization: {org.get('name', 'Unknown')}")
                if org.get("id"):
                    content_parts.append(f"  Organization ID: {org.get('id')}")

        # Handle tags
        tags = []
        for tag in data.get("tags", []):
            if isinstance(tag, str):
                tags.append(tag)
            elif isinstance(tag, dict):
                tag_name = tag.get("name", "")
                if tag_name:
                    tags.append(tag_name)
        if tags:
            content_parts.append("")
            content_parts.append(f"Tags: {', '.join(tags[:10])}")

        # Resources info
        resources = data.get("resources", [])
        content_parts.append("")
        content_parts.append(f"Resources: {len(resources)} file(s)")

        # Dates
        if data.get("created_at"):
            content_parts.append("")
            content_parts.append(f"Created: {data.get('created_at')}")
        if data.get("last_update"):
            content_parts.append(f"Last updated: {data.get('last_update')}")

        # License
        if data.get("license"):
            content_parts.append("")
            content_parts.append(f"License: {data.get('license')}")

        # Frequency
        if data.get("frequency"):
            content_parts.append(f"Update frequency: {data.get('frequency')}")

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        return f"Error: HTTP {e.status} - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def list_dataset_resources(dataset_id: str) -> str:
    """
    List all resources (files) in a dataset with their metadata.

    Returns information about each resource including ID, title, format, size,
    and type. Useful for understanding what data files are available in a dataset
    before querying them.

    Args:
        dataset_id: The ID of the dataset to list resources from

    Returns:
        Formatted text listing all resources with their metadata
    """
    try:
        result = await datagouv_api_client.get_resources_for_dataset(dataset_id)
        dataset = result.get("dataset", {})
        resources = result.get("resources", [])

        if not dataset.get("id"):
            return f"Error: Dataset with ID '{dataset_id}' not found."

        dataset_title = dataset.get("title", "Unknown")

        content_parts = [
            f"Resources in dataset: {dataset_title}",
            f"Dataset ID: {dataset_id}",
            f"Total resources: {len(resources)}\n",
        ]

        if not resources:
            content_parts.append("This dataset has no resources.")
            return "\n".join(content_parts)

        # Get detailed info for each resource
        async with aiohttp.ClientSession() as session:
            for i, (resource_id, resource_title) in enumerate(resources, 1):
                content_parts.append(f"{i}. {resource_title or 'Untitled'}")
                content_parts.append(f"   Resource ID: {resource_id}")

                try:
                    # Get full resource metadata
                    url = f"{datagouv_api_client.api_base_url()}2/datasets/resources/{resource_id}/"
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        if resp.status == 200:
                            resource_data = await resp.json()
                            resource = resource_data.get("resource", {})

                            if resource.get("format"):
                                content_parts.append(
                                    f"   Format: {resource.get('format')}"
                                )
                            if resource.get("filesize"):
                                size = resource.get("filesize")
                                if isinstance(size, int):
                                    # Format size in human-readable format
                                    if size < 1024:
                                        size_str = f"{size} B"
                                    elif size < 1024 * 1024:
                                        size_str = f"{size / 1024:.1f} KB"
                                    elif size < 1024 * 1024 * 1024:
                                        size_str = f"{size / (1024 * 1024):.1f} MB"
                                    else:
                                        size_str = (
                                            f"{size / (1024 * 1024 * 1024):.1f} GB"
                                        )
                                    content_parts.append(f"   Size: {size_str}")
                            if resource.get("mime"):
                                content_parts.append(
                                    f"   MIME type: {resource.get('mime')}"
                                )
                            if resource.get("type"):
                                content_parts.append(f"   Type: {resource.get('type')}")
                            if resource.get("url"):
                                content_parts.append(f"   URL: {resource.get('url')}")
                except Exception as e:
                    logger.warning(
                        f"Could not fetch details for resource {resource_id}: {e}"
                    )

                content_parts.append("")

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        return f"Error: HTTP {e.status} - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_resource_info(resource_id: str) -> str:
    """
    Get detailed information about a specific resource (file).

    Returns comprehensive metadata including format, size, MIME type, URL,
    and associated dataset information. Useful for understanding a resource
    before querying its data.

    Args:
        resource_id: The ID of the resource to get information about

    Returns:
        Formatted text with detailed resource information
    """
    try:
        # Get resource metadata
        resource_meta = await datagouv_api_client.get_resource_metadata(resource_id)
        if not resource_meta.get("id"):
            return f"Error: Resource with ID '{resource_id}' not found."

        content_parts = [
            f"Resource Information: {resource_meta.get('title', 'Unknown')}",
            "",
            f"Resource ID: {resource_id}",
        ]

        # Get full resource data from API v2
        url = f"{datagouv_api_client.api_base_url()}2/datasets/resources/{resource_id}/"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 404:
                    return f"Error: Resource with ID '{resource_id}' not found."
                resp.raise_for_status()
                data = await resp.json()

        resource = data.get("resource", {})

        if resource.get("format"):
            content_parts.append(f"Format: {resource.get('format')}")

        if resource.get("filesize"):
            size = resource.get("filesize")
            if isinstance(size, int):
                # Format size in human-readable format
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                else:
                    size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
                content_parts.append(f"Size: {size_str}")

        if resource.get("mime"):
            content_parts.append(f"MIME type: {resource.get('mime')}")

        if resource.get("type"):
            content_parts.append(f"Type: {resource.get('type')}")

        if resource.get("url"):
            content_parts.append("")
            content_parts.append(f"URL: {resource.get('url')}")

        if resource.get("description"):
            content_parts.append("")
            content_parts.append(f"Description: {resource.get('description')}")

        # Dataset information
        dataset_id = data.get("dataset_id") or resource_meta.get("dataset_id")
        if dataset_id:
            content_parts.append("")
            content_parts.append(f"Dataset ID: {dataset_id}")
            try:
                dataset_meta = await datagouv_api_client.get_dataset_metadata(
                    str(dataset_id)
                )
                if dataset_meta.get("title"):
                    content_parts.append(f"Dataset: {dataset_meta.get('title')}")
            except Exception:
                pass

        # Check if resource is available via Tabular API
        content_parts.append("")
        try:
            # Try to get profile to check if it's tabular
            profile_url = f"{datagouv_api_client.tabular_api_base_url()}resources/{resource_id}/profile/"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    profile_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        content_parts.append(
                            "✅ Available via Tabular API (can be queried)"
                        )
                    else:
                        content_parts.append(
                            "⚠️  Not available via Tabular API (may not be tabular data)"
                        )
        except Exception:
            content_parts.append("⚠️  Could not check Tabular API availability")

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        return f"Error: HTTP {e.status} - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


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


async def _download_resource(
    resource_url: str, max_size: int = 500 * 1024 * 1024
) -> tuple[bytes, str, str | None]:
    """
    Download a resource with size limit.

    Returns:
        (content, filename, content_type)
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            resource_url, timeout=aiohttp.ClientTimeout(total=300)
        ) as resp:
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
            content = b""
            async for chunk in resp.content.iter_chunked(8192):
                content += chunk
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

            return content, filename, content_type


def _parse_csv(content: bytes, is_gzipped: bool = False) -> list[dict[str, Any]]:
    """Parse CSV content."""
    if is_gzipped:
        content = gzip.decompress(content)

    text = content.decode("utf-8-sig")  # Handle BOM
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def _parse_json(content: bytes, is_gzipped: bool = False) -> list[dict[str, Any]]:
    """Parse JSON content (array or JSONL)."""
    if is_gzipped:
        content = gzip.decompress(content)

    text = content.decode("utf-8")

    # Try JSON array first
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
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


@mcp.tool()
async def download_and_parse_resource(
    resource_id: str,
    max_rows: int = 1000,
    max_size_mb: int = 500,
) -> str:
    """
    Download and parse a resource that is not accessible via Tabular API.

    This tool is useful for:
    - Files larger than Tabular API limits (CSV > 100 MB, XLSX > 12.5 MB)
    - Formats not supported by Tabular API (JSON, XML, etc.)
    - Files with external URLs

    Supported formats: CSV, CSV.GZ, JSON, JSONL, XLSX (if openpyxl available)

    Args:
        resource_id: The ID of the resource to download and parse
        max_rows: Maximum number of rows to return (default: 1000)
        max_size_mb: Maximum file size to download in MB (default: 500)

    Returns:
        Formatted text with the parsed data
    """
    try:
        # Get resource metadata to find URL
        resource_meta = await datagouv_api_client.get_resource_metadata(resource_id)
        if not resource_meta.get("id"):
            return f"Error: Resource with ID '{resource_id}' not found."

        # Get full resource data to get URL
        url = f"{datagouv_api_client.api_base_url()}2/datasets/resources/{resource_id}/"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 404:
                    return f"Error: Resource with ID '{resource_id}' not found."
                resp.raise_for_status()
                data = await resp.json()

        resource = data.get("resource", {})
        resource_url = resource.get("url")
        if not resource_url:
            return f"Error: Resource {resource_id} has no download URL."

        resource_title = resource.get("title") or resource_meta.get("title", "Unknown")

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
        except Exception as e:
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
            content_parts.append("Supported formats: CSV, CSV.GZ, JSON, JSONL, XLSX")
            return "\n".join(content_parts)

        # Parse according to format
        rows = []
        try:
            if file_format == "csv" or (
                file_format == "gzip" and "csv" in filename.lower()
            ):
                content_parts.append("Format: CSV")
                rows = _parse_csv(content, is_gzipped=is_gzipped)
            elif file_format == "json" or file_format == "jsonl":
                content_parts.append("Format: JSON/JSONL")
                rows = _parse_json(content, is_gzipped=is_gzipped)
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

        except Exception as e:
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

        # Show sample data
        content_parts.append("")
        content_parts.append("Sample data (first 3 rows):")
        for i, row in enumerate(rows[:3], 1):
            content_parts.append(f"  Row {i}:")
            for key, value in row.items():
                val_str = str(value) if value is not None else ""
                if len(val_str) > 100:
                    val_str = val_str[:100] + "..."
                content_parts.append(f"    {key}: {val_str}")

        if len(rows) > 3:
            content_parts.append(f"  ... ({len(rows) - 3} more row(s) available)")

        if total_rows > max_rows:
            content_parts.append("")
            content_parts.append(
                f"⚠️  Note: File contains {total_rows} rows, "
                f"only showing first {max_rows}. "
                "Increase max_rows parameter to see more."
            )

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        return f"Error: HTTP {e.status} - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


# Run with streamable HTTP transport
if __name__ == "__main__":
    port_str = os.getenv("MCP_PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(
            f"Error: Invalid MCP_PORT environment variable: {port_str}",
            file=sys.stderr,
        )
        sys.exit(1)
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port, log_level="info")
