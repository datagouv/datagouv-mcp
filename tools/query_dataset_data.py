import logging

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, tabular_api_client

logger = logging.getLogger("datagouv_mcp")


def register_query_dataset_data_tool(mcp: FastMCP) -> None:
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
                        content_parts.append(
                            f"  Total rows (Tabular API): {total_count}"
                        )
                    content_parts.append(f"  Retrieved: {len(rows)} row(s)")
                    if page_info is not None and page_size_meta is not None:
                        content_parts.append(
                            f"  Page info: page {page_info} (page size {page_size_meta})"
                        )

                    # Show column names
                    if rows:
                        columns = [
                            str(k) if k is not None else "" for k in rows[0].keys()
                        ]
                        content_parts.append(f"  Columns: {', '.join(columns)}")

                    if not rows:
                        content_parts.append("")
                        continue

                    # Show sample data (first few rows)
                    content_parts.append("\n  Sample data (first 3 rows):")
                    for i, row in enumerate(rows[:3], 1):
                        content_parts.append(f"    Row {i}:")
                        for key, value in row.items():
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
                except httpx.HTTPStatusError as e:
                    error_details = f"HTTP {e.response.status_code}: {str(e)}"
                    if e.request:
                        error_details += f" - URL: {e.request.url}"
                    logger.error(
                        f"Tabular API HTTP error for resource {resource_id}: {error_details}"
                    )

                    content_parts.append(f"  ❌ Tabular API error ({error_details})")
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        f"Unexpected error exploring resource {resource_id}"
                    )
                    content_parts.append(f"  ❌ Error exploring table: {str(e)}")

                content_parts.append("")

            if not found_data:
                content_parts.append(
                    "⚠️  No data tables were found or accessible for the resources in this dataset."
                )

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
