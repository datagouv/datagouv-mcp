import logging

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, tabular_api_client

logger = logging.getLogger("datagouv_mcp")


def register_query_resource_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def query_resource_data(
        question: str,
        resource_id: str,
        page: int = 1,
    ) -> str:
        """
        Query data from a specific resource (file) via the Tabular API.

        The Tabular API is data.gouv.fr's API for parsing and querying the content of
        resources (files) on the platform. It allows you to access structured data from
        tabular files (CSV, XLSX, etc.) without downloading the entire file. This tool
        fetches rows from a specific resource using this API.

        Each call retrieves up to 200 rows (the maximum allowed by the API).

        Note: The Tabular API has size limits (CSV > 100 MB, XLSX > 12.5 MB are not
        supported). For larger files or unsupported formats, use download_and_parse_resource.
        You can use get_resource_info to check if a resource is available via Tabular API.

        Recommended workflow:
        1. Use search_datasets to find the appropriate dataset
        2. Use list_dataset_resources to see available resources (files) in the dataset
        3. (Optional) Use get_resource_info to verify Tabular API availability
        4. Use query_resource_data with the chosen resource_id to fetch data
        5. If the answer is not in the first page, use query_resource_data with page=2, page=3, etc.

        Args:
            question: The question or description of what data you're looking for (for context)
            resource_id: Resource ID (use list_dataset_resources to find resource IDs)
            page: Page number to retrieve (default: 1). Use this to navigate through large datasets.
                  Each page contains up to 200 rows.

        Returns:
            Formatted text with the data found from the resource, including pagination info
        """
        try:
            # Get resource metadata to display context
            try:
                resource_metadata = await datagouv_api_client.get_resource_metadata(
                    resource_id
                )
                resource_title = resource_metadata.get("title", "Unknown")
                dataset_id = resource_metadata.get("dataset_id")
            except Exception:  # noqa: BLE001
                resource_title = "Unknown"
                dataset_id = None

            # Get dataset title if available
            dataset_title = "Unknown"
            if dataset_id:
                try:
                    dataset_metadata = await datagouv_api_client.get_dataset_metadata(
                        str(dataset_id)
                    )
                    dataset_title = dataset_metadata.get("title", "Unknown")
                except Exception:  # noqa: BLE001
                    pass

            content_parts = [
                f"Querying resource: {resource_title}",
                f"Resource ID: {resource_id}",
            ]
            if dataset_id:
                content_parts.append(f"Dataset: {dataset_title} (ID: {dataset_id})")
            content_parts.extend(
                [
                    f"Question: {question}",
                    "",
                ]
            )

            # Fetch data via the Tabular API (always use max page size of 200)
            page_size = 200
            logger.info(
                f"Querying Tabular API for resource: {resource_title} "
                f"(ID: {resource_id}), page: {page}, page_size: {page_size}"
            )

            try:
                tabular_data = await tabular_api_client.fetch_resource_data(
                    resource_id, page=page, page_size=page_size
                )
                rows = tabular_data.get("data", [])
                meta = tabular_data.get("meta", {})
                total_count = meta.get("total")
                page_info = meta.get("page")
                page_size_meta = meta.get("page_size")

                if not rows:
                    content_parts.append(
                        "⚠️  No rows available (resource may be empty or filtered)."
                    )
                    return "\n".join(content_parts)

                if total_count is not None:
                    content_parts.append(f"Total rows (Tabular API): {total_count}")
                    # Calculate total pages
                    if page_size_meta and page_size_meta > 0:
                        total_pages = (
                            total_count + page_size_meta - 1
                        ) // page_size_meta
                        content_parts.append(
                            f"Total pages: {total_pages} (page size: {page_size_meta})"
                        )
                content_parts.append(
                    f"Retrieved: {len(rows)} row(s) from page {page_info or page}"
                )

                # Show column names
                if rows:
                    columns = [str(k) if k is not None else "" for k in rows[0].keys()]
                    content_parts.append(f"Columns: {', '.join(columns)}")

                # Show sample data (first few rows)
                content_parts.append("\nSample data (first 3 rows):")
                for i, row in enumerate(rows[:3], 1):
                    content_parts.append(f"  Row {i}:")
                    for key, value in row.items():
                        val_str = str(value) if value is not None else ""
                        if len(val_str) > 100:
                            val_str = val_str[:100] + "..."
                        content_parts.append(f"    {key}: {val_str}")

                if len(rows) > 3:
                    content_parts.append(
                        f"  ... ({len(rows) - 3} more row(s) available)"
                    )

                links = tabular_data.get("links", {})
                if links.get("next"):
                    next_page = page + 1
                    content_parts.append("")
                    content_parts.append(
                        f"📄 More data available! To see the next page, call query_resource_data "
                        f"again with page={next_page} (and the same resource_id and question)."
                    )
                    if total_count and page_size_meta:
                        remaining_pages = (
                            (total_count + page_size_meta - 1) // page_size_meta
                        ) - page
                        if remaining_pages > 1:
                            content_parts.append(
                                f"   There are {remaining_pages} more page(s) available after this one."
                            )

            except tabular_api_client.ResourceNotAvailableError as e:
                logger.warning(f"Resource not available: {resource_id} - {str(e)}")
                content_parts.append(f"⚠️  {str(e)}")
            except httpx.HTTPStatusError as e:
                error_details = f"HTTP {e.response.status_code}: {str(e)}"
                if e.request:
                    error_details += f" - URL: {e.request.url}"
                logger.error(
                    f"Tabular API HTTP error for resource {resource_id}: {error_details}"
                )
                content_parts.append(f"❌ Tabular API error ({error_details})")
            except Exception as e:  # noqa: BLE001
                logger.exception(f"Unexpected error querying resource {resource_id}")
                content_parts.append(f"❌ Error querying resource: {str(e)}")

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
