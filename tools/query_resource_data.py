import logging

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, tabular_api_client
from helpers.formatting import truncate_text

logger = logging.getLogger("datagouv_mcp")


def register_query_resource_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def query_resource_data(
        question: str,
        resource_id: str,
        page: int = 1,
        page_size: int = 20,
        filter_column: str | None = None,
        filter_value: str | None = None,
        filter_operator: str = "exact",
        sort_column: str | None = None,
        sort_direction: str = "asc",
    ) -> str:
        """
        Query tabular data from a resource via the Tabular API (no download needed).

        Works for CSV/XLSX files. Start with small page_size (20) to preview structure.
        Use filter_column/filter_value/filter_operator to filter, sort_column/sort_direction to sort.
        Filter operators: exact, contains, less, greater, strictly_less, strictly_greater.
        For large datasets (>1000 rows) requiring full analysis, download_and_parse_resource
        may be more efficient than paginating through many pages.
        """
        try:
            filter_operator = filter_operator.lower()
            sort_direction = sort_direction.lower()

            operator_map = {
                "exact": "exact",
                "contains": "contains",
                "less": "less",
                "greater": "greater",
                "strictly_less": "strictly_less",
                "strictly_greater": "strictly_greater",
            }
            if filter_column and filter_value is not None:
                if filter_operator not in operator_map:
                    supported = ", ".join(sorted(operator_map.keys()))
                    return (
                        "Error: invalid filter_operator. "
                        f"Supported values: {supported}."
                    )

            if sort_column and sort_direction not in {"asc", "desc"}:
                return "Error: invalid sort_direction. Supported values: asc, desc."

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

            # Show applied filters if any
            if filter_column and filter_value is not None:
                content_parts.append(
                    f"Filter: {filter_column} {filter_operator} {filter_value}"
                )
            if sort_column:
                content_parts.append(f"Sort: {sort_column} ({sort_direction})")
            if filter_column or sort_column:
                content_parts.append("")

            # Fetch data via the Tabular API (clamp page_size to valid range)
            page_size = max(1, min(page_size, 200))

            # Build filter and sort parameters for Tabular API
            api_params = {}

            # Add filter if provided
            if filter_column and filter_value is not None:
                operator = operator_map[filter_operator]
                param_key = f"{filter_column}__{operator}"
                api_params[param_key] = filter_value

            # Add sort if provided
            if sort_column:
                api_params[f"{sort_column}__sort"] = sort_direction

            logger.info(
                f"Querying Tabular API for resource: {resource_title} "
                f"(ID: {resource_id}), page: {page}, page_size: {page_size}, "
                f"filters: {api_params}"
            )

            try:
                tabular_data = await tabular_api_client.fetch_resource_data(
                    resource_id,
                    page=page,
                    page_size=page_size,
                    params=api_params if api_params else None,
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

                # Show all retrieved data
                content_parts.append("")
                if len(rows) == 1:
                    content_parts.append("Data (1 row):")
                else:
                    content_parts.append(f"Data ({len(rows)} rows):")
                for i, row in enumerate(rows, 1):
                    content_parts.append(f"  Row {i}:")
                    for key, value in row.items():
                        val_str = str(value) if value is not None else ""
                        val_str = truncate_text(val_str, 100)
                        content_parts.append(f"    {key}: {val_str}")

                links = tabular_data.get("links", {})
                if links.get("next"):
                    next_page = page + 1
                    content_parts.append("")

                    # Adapt message based on dataset size
                    if total_count and total_count > 1000:
                        content_parts.append(
                            f"⚠️ Large dataset ({total_count} rows). "
                            f"For comprehensive analysis, consider using download_and_parse_resource "
                            f"instead of paginating through many pages."
                        )
                        content_parts.append(
                            f"   If you only need specific data, you can continue with page={next_page}."
                        )
                    else:
                        content_parts.append(
                            f"📄 More data available. Use page={next_page} to see the next page."
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
