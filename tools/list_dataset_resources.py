from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, DataTable, DataTableColumn

from helpers import datagouv_api_client
from helpers.logging import log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def _format_filesize(size: int | None) -> str:
    if size is None:
        return ""
    if not isinstance(size, int):
        return str(size)
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


async def _list_dataset_resources_data(
    dataset_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Return markdown-style text and flat rows for optional DataTable."""
    try:
        dataset = await datagouv_api_client.get_dataset_details(dataset_id)
        resources = dataset.get("resources", [])

        if not dataset.get("id"):
            return f"Error: Dataset with ID '{dataset_id}' not found.", []

        dataset_title = dataset.get("title", "Unknown")

        content_parts = [
            f"Resources in dataset: {dataset_title}",
            f"Dataset ID: {dataset_id}",
            f"Total resources: {len(resources)}\n",
        ]

        rows: list[dict[str, Any]] = []

        if not resources:
            content_parts.append("This dataset has no resources.")
            return "\n".join(content_parts), []

        for i, resource in enumerate(resources, 1):
            resource_id = resource.get("id")
            if not resource_id:
                continue
            resource_title = resource.get("title") or resource.get("name")
            title_display = resource_title or "Untitled"
            format_str = str(resource.get("format") or "")
            size_str = ""
            if resource.get("filesize"):
                size_str = _format_filesize(resource.get("filesize"))
            mime_str = str(resource.get("mime") or "")
            type_str = str(resource.get("type") or "")
            url_str = str(resource.get("url") or "")

            content_parts.append(f"{i}. {title_display}")
            content_parts.append(f"   Resource ID: {resource_id}")
            if format_str:
                content_parts.append(f"   Format: {format_str}")
            if size_str:
                content_parts.append(f"   Size: {size_str}")
            if mime_str:
                content_parts.append(f"   MIME type: {mime_str}")
            if type_str:
                content_parts.append(f"   Type: {type_str}")
            if url_str:
                content_parts.append(f"   URL: {url_str}")
            content_parts.append("")

            rows.append(
                {
                    "#": i,
                    "title": title_display,
                    "resource_id": str(resource_id),
                    "format": format_str or "—",
                    "size": size_str or "—",
                    "mime": mime_str or "—",
                    "url": url_str or "—",
                }
            )

        return "\n".join(content_parts), rows
    except Exception as e:  # noqa: BLE001
        return f"Error: {str(e)}", []


def _list_resources_prefab(rows: list[dict[str, Any]]) -> PrefabApp:
    with PrefabApp() as app:
        with Column(gap=4):
            DataTable(
                columns=[
                    DataTableColumn(key="#", header="#", sortable=True),
                    DataTableColumn(key="title", header="Title", sortable=True),
                    DataTableColumn(
                        key="resource_id", header="Resource ID", sortable=True
                    ),
                    DataTableColumn(key="format", header="Format", sortable=True),
                    DataTableColumn(key="size", header="Size", sortable=True),
                    DataTableColumn(key="mime", header="MIME", sortable=True),
                    DataTableColumn(key="url", header="URL", sortable=False),
                ],
                rows=rows,  # ty: ignore[invalid-argument-type]
                search=True,
            )
    return app


def register_list_dataset_resources_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="List dataset resources",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def list_dataset_resources(dataset_id: str) -> str:
        """
        List all resources (files) in a dataset with their metadata.

        Returns resource ID, title, format, size, and URL for each file.
        Next step: use query_resource_data for CSV/XLSX files via the Tabular API,
        or fetch the resource URL directly for other formats (JSON, JSONL) or large datasets.
        """
        text, _rows = await _list_dataset_resources_data(dataset_id)
        return text


def register_list_dataset_resources_visual_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="List dataset resources (visual)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def list_dataset_resources_visual(dataset_id: str) -> ToolResult:
        """
        Same as list_dataset_resources with a sortable, searchable table where supported.
        """
        text, rows = await _list_dataset_resources_data(dataset_id)
        if not rows:
            return ToolResult(content=text, structured_content=None)
        return ToolResult(
            content=text,
            structured_content=_list_resources_prefab(rows),
        )
