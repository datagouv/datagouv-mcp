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
        limit: int = 100,
    ) -> str:
        """
        Query data from a specific resource via the Tabular API.

        This tool fetches rows from a specific resource (file) using the data.gouv.fr
        Tabular API. Use this tool after identifying the resource you want to query
        via list_dataset_resources.

        Recommended workflow:
        1. Use search_datasets to find the appropriate dataset
        2. Use list_dataset_resources to see available resources in the dataset
        3. Use query_resource_data with the chosen resource_id to fetch data

        Args:
            question: The question or description of what data you're looking for
            resource_id: Resource ID (use list_dataset_resources to find resource IDs)
            limit: Maximum number of rows to retrieve (default: 100, max: 200)

        Returns:
            Formatted text with the data found from the resource
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

            # Fetch data via the Tabular API
            page_size = max(1, min(limit, 200))
            logger.info(
                f"Querying Tabular API for resource: {resource_title} "
                f"(ID: {resource_id}), page_size: {page_size}"
            )

            try:
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
                        "⚠️  No rows available (resource may be empty or filtered)."
                    )
                    return "\n".join(content_parts)

                if total_count is not None:
                    content_parts.append(f"Total rows (Tabular API): {total_count}")
                content_parts.append(f"Retrieved: {len(rows)} row(s)")
                if page_info is not None and page_size_meta is not None:
                    content_parts.append(
                        f"Page info: page {page_info} (page size {page_size_meta})"
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
                    content_parts.append(
                        "More data available via Tabular API (next page link provided)."
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
