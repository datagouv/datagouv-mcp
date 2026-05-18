import logging
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, DataTable, DataTableColumn

from helpers import datagouv_api_client, tabular_api_client
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL

logger = logging.getLogger(MAIN_LOGGER_NAME)


def _tabular_rows_for_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce cell values to strings for stable Prefab/DataTable display."""
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({str(k): _cell_to_str(v) for k, v in row.items()})
    return out


def _cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value)
    if len(s) > 500:
        return s[:500] + "..."
    return s


def _query_resource_data_prefab(rows: list[dict[str, Any]]) -> PrefabApp:
    if not rows:
        return PrefabApp()
    keys = list(rows[0].keys())
    columns = [DataTableColumn(key=k, header=k, sortable=True) for k in keys]
    with PrefabApp() as app:
        with Column(gap=4):
            DataTable(columns=columns, rows=rows, search=True)
    return app


async def _query_resource_data_core(
    resource_id: str,
    page: int = 1,
    page_size: int = 20,
    filter_column: str | None = None,
    filter_value: str | None = None,
    filter_operator: str = "exact",
    sort_column: str | None = None,
    sort_direction: str = "asc",
) -> tuple[str, list[dict[str, Any]]]:
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
                f"Error: invalid filter_operator. Supported values: {supported}.",
                [],
            )

    if sort_column and sort_direction not in {"asc", "desc"}:
        return (
            "Error: invalid sort_direction. Supported values: asc, desc.",
            [],
        )

    try:
        try:
            resource_metadata = await datagouv_api_client.get_resource_metadata(
                resource_id
            )
            resource_title = resource_metadata.get("title", "Unknown")
            dataset_id = resource_metadata.get("dataset_id")
        except Exception:  # noqa: BLE001
            resource_title = "Unknown"
            dataset_id = None

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
        content_parts.append("")

        if filter_column and filter_value is not None:
            content_parts.append(
                f"Filter: {filter_column} {filter_operator} {filter_value}"
            )
        if sort_column:
            content_parts.append(f"Sort: {sort_column} ({sort_direction})")
        if filter_column or sort_column:
            content_parts.append("")

        page_size = max(1, min(page_size, 200))

        api_params: dict[str, str] = {}
        if filter_column and filter_value is not None:
            op = operator_map[filter_operator]
            param_key = f"{filter_column}__{op}"
            api_params[param_key] = filter_value

        if sort_column:
            api_params[f"{sort_column}__sort"] = sort_direction

        logger.info(
            "Querying Tabular API for resource: %s (ID: %s), page: %s, page_size: %s, filters: %s",
            resource_title,
            resource_id,
            page,
            page_size,
            api_params,
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
                return "\n".join(content_parts), []

            if total_count is not None:
                content_parts.append(f"Total rows (Tabular API): {total_count}")
                if page_size_meta and page_size_meta > 0:
                    total_pages = (total_count + page_size_meta - 1) // page_size_meta
                    content_parts.append(
                        f"Total pages: {total_pages} (page size: {page_size_meta})"
                    )
            content_parts.append(
                f"Retrieved: {len(rows)} row(s) from page {page_info or page}"
            )

            if rows:
                columns = [str(k) if k is not None else "" for k in rows[0].keys()]
                content_parts.append(f"Columns: {', '.join(columns)}")

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

            links = tabular_data.get("links", {})
            if links.get("next"):
                next_page = page + 1
                content_parts.append("")
                if total_count and total_count > 1000:
                    content_parts.append(
                        f"⚠️ Large dataset ({total_count} rows). "
                        f"To get all data, paginate using page={next_page} or use "
                        "get_resource_info to retrieve the raw file URL and fetch it directly."
                    )
                else:
                    content_parts.append(
                        f"📄 More data available. Use page={next_page} to see the next page."
                    )

            table_rows = _tabular_rows_for_table(rows)
            return "\n".join(content_parts), table_rows

        except tabular_api_client.ResourceNotAvailableError as e:
            logger.warning("Resource not available: %s - %s", resource_id, str(e))
            content_parts.append(f"⚠️  {str(e)}")
        except tabular_api_client.TabularApiRequestError as e:
            logger.warning("Tabular API request failed: %s - %s", resource_id, str(e))
            content_parts.append(f"⚠️  {str(e)}")
        except httpx.HTTPStatusError as e:
            error_details = f"HTTP {e.response.status_code}: {str(e)}"
            if e.request:
                error_details += f" - URL: {e.request.url}"
            logger.warning(
                "Tabular API HTTP error for resource %s: %s",
                resource_id,
                error_details,
            )
            content_parts.append(f"❌ Tabular API error ({error_details})")
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error querying resource %s", resource_id)
            content_parts.append(f"❌ Error querying resource: {str(e)}")

        return "\n".join(content_parts), []

    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} - {str(e)}", []
    except Exception as e:  # noqa: BLE001
        return f"Error: {str(e)}", []


def register_query_resource_data_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Query resource data",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def query_resource_data(
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
        For large datasets requiring full analysis, paginate through pages or use
        get_resource_info to retrieve the raw file URL and fetch it directly.
        """
        text, _rows = await _query_resource_data_core(
            resource_id,
            page,
            page_size,
            filter_column,
            filter_value,
            filter_operator,
            sort_column,
            sort_direction,
        )
        return text


def register_query_resource_data_visual_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Query resource data (visual)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def query_resource_data_visual(
        resource_id: str,
        page: int = 1,
        page_size: int = 20,
        filter_column: str | None = None,
        filter_value: str | None = None,
        filter_operator: str = "exact",
        sort_column: str | None = None,
        sort_direction: str = "asc",
    ) -> ToolResult:
        """
        Same as query_resource_data with a sortable table for the current page.
        """
        text, rows = await _query_resource_data_core(
            resource_id,
            page,
            page_size,
            filter_column,
            filter_value,
            filter_operator,
            sort_column,
            sort_direction,
        )
        if not rows:
            return ToolResult(content=text, structured_content=None)
        return ToolResult(
            content=text,
            structured_content=_query_resource_data_prefab(rows),
        )
