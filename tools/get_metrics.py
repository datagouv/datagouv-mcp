import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, DataTable, DataTableColumn, Separator, Text
from prefab_ui.components.charts import BarChart, ChartSeries

from helpers import datagouv_api_client, metrics_api_client
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL

logger = logging.getLogger(MAIN_LOGGER_NAME)


@dataclass
class _MetricsPanel:
    """One metrics block (dataset and/or resource) for text and Prefab output."""

    kind: Literal["dataset", "resource"]
    metadata_lines: list[str]
    rows: list[dict[str, Any]]
    fetch_error: str | None = None
    empty_message: str | None = None


def _metrics_panels_to_text(panels: list[_MetricsPanel]) -> str:
    content_parts: list[str] = []
    for i, panel in enumerate(panels):
        if i > 0:
            content_parts.extend(["", ""])
        content_parts.extend(panel.metadata_lines)
        if panel.fetch_error:
            content_parts.append(panel.fetch_error)
            continue
        if not panel.rows:
            if panel.empty_message:
                content_parts.append(panel.empty_message)
            continue
        if panel.kind == "dataset":
            content_parts.append("Monthly Statistics:")
            content_parts.append("-" * 60)
            content_parts.append(f"{'Month':<12} {'Visits':<15} {'Downloads':<15}")
            content_parts.append("-" * 60)
            total_visits = 0
            total_downloads = 0
            for entry in panel.rows:
                month = str(entry.get("month", "Unknown"))
                visits = int(entry.get("visits", 0) or 0)
                downloads = int(entry.get("downloads", 0) or 0)
                total_visits += visits
                total_downloads += downloads
                content_parts.append(f"{month:<12} {visits:<15,} {downloads:<15,}")
            content_parts.append("-" * 60)
            content_parts.append(
                f"{'Total':<12} {total_visits:<15,} {total_downloads:<15,}"
            )
        else:
            content_parts.append("Monthly Statistics:")
            content_parts.append("-" * 40)
            content_parts.append(f"{'Month':<12} {'Downloads':<15}")
            content_parts.append("-" * 40)
            total_downloads = 0
            for entry in panel.rows:
                month = str(entry.get("month", "Unknown"))
                downloads = int(entry.get("downloads", 0) or 0)
                total_downloads += downloads
                content_parts.append(f"{month:<12} {downloads:<15,}")
            content_parts.append("-" * 40)
            content_parts.append(f"{'Total':<12} {total_downloads:<15,}")
    return "\n".join(content_parts)


def _build_metrics_prefab(panels: list[_MetricsPanel]) -> PrefabApp:
    with PrefabApp() as app:
        with Column(gap=4):
            for pi, panel in enumerate(panels):
                if pi > 0:
                    Separator()
                for line in panel.metadata_lines:
                    if line.strip():
                        Text(line)
                if panel.fetch_error:
                    Text(panel.fetch_error)
                elif not panel.rows:
                    if panel.empty_message:
                        Text(panel.empty_message)
                elif panel.kind == "dataset":
                    BarChart(
                        data=panel.rows,
                        series=[
                            ChartSeries(dataKey="visits", label="Visits"),
                            ChartSeries(dataKey="downloads", label="Downloads"),
                        ],
                        xAxis="month",
                    )
                    DataTable(
                        columns=[
                            DataTableColumn(key="month", header="Month", sortable=True),
                            DataTableColumn(
                                key="visits", header="Visits", sortable=True
                            ),
                            DataTableColumn(
                                key="downloads", header="Downloads", sortable=True
                            ),
                        ],
                        rows=panel.rows,  # ty: ignore[invalid-argument-type]
                        search=True,
                    )
                else:
                    BarChart(
                        data=panel.rows,
                        series=[
                            ChartSeries(dataKey="downloads", label="Downloads"),
                        ],
                        xAxis="month",
                    )
                    DataTable(
                        columns=[
                            DataTableColumn(key="month", header="Month", sortable=True),
                            DataTableColumn(
                                key="downloads", header="Downloads", sortable=True
                            ),
                        ],
                        rows=panel.rows,  # ty: ignore[invalid-argument-type]
                        search=True,
                    )
    return app


async def _run_metrics_core(
    dataset_id: str | None,
    resource_id: str | None,
    limit: int,
) -> tuple[str, list[_MetricsPanel]]:
    current_env: str = os.getenv("DATAGOUV_API_ENV", "prod").strip().lower()
    if current_env == "demo":
        return (
            (
                "Error: The Metrics API is not available in the demo environment.\n"
                "The Metrics API only exists in production. Please set DATAGOUV_API_ENV=prod "
                "to use this tool, or switch to production environment to access metrics data."
            ),
            [],
        )

    if not dataset_id and not resource_id:
        return (
            "Error: At least one of dataset_id or resource_id must be provided.",
            [],
        )

    panels: list[_MetricsPanel] = []
    limit = max(1, min(limit, 50))

    try:
        if dataset_id:
            dataset_id = str(dataset_id).strip()
            if not dataset_id:
                return ("Error: dataset_id cannot be empty.", [])

            logger.debug("Fetching metrics for dataset_id: %s", dataset_id)

            meta_lines: list[str] = []
            try:
                dataset_meta = await datagouv_api_client.get_dataset_metadata(
                    dataset_id
                )
                dataset_title = dataset_meta.get("title", "Unknown")
                meta_lines.extend(
                    [
                        f"Dataset Metrics: {dataset_title}",
                        f"Dataset ID: {dataset_id}",
                        "",
                    ]
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not fetch dataset metadata: %s", e)
                meta_lines.extend(
                    [
                        "Dataset Metrics",
                        f"Dataset ID: {dataset_id}",
                        "",
                    ]
                )

            fetch_error: str | None = None
            rows: list[dict[str, Any]] = []
            try:
                logger.debug(
                    "Calling metrics_api_client.get_metrics with dataset_id: %s",
                    dataset_id,
                )
                metrics = await metrics_api_client.get_metrics(
                    "datasets", dataset_id, limit=limit
                )
                logger.debug(
                    "Received %s metric entries",
                    len(metrics) if metrics else 0,
                )
                if not metrics:
                    panels.append(
                        _MetricsPanel(
                            kind="dataset",
                            metadata_lines=meta_lines,
                            rows=[],
                            empty_message="No metrics available for this dataset.",
                        )
                    )
                else:
                    for entry in metrics:
                        rows.append(
                            {
                                "month": entry.get("metric_month", "Unknown"),
                                "visits": entry.get("monthly_visit", 0) or 0,
                                "downloads": entry.get("monthly_download_resource", 0)
                                or 0,
                            }
                        )
                    panels.append(
                        _MetricsPanel(
                            kind="dataset",
                            metadata_lines=meta_lines,
                            rows=rows,
                        )
                    )
            except Exception as e:  # noqa: BLE001
                logger.error("Error fetching dataset metrics: %s", e)
                fetch_error = f"Error fetching dataset metrics: {str(e)}"
                panels.append(
                    _MetricsPanel(
                        kind="dataset",
                        metadata_lines=meta_lines,
                        rows=[],
                        fetch_error=fetch_error,
                    )
                )

        if resource_id:
            resource_id = str(resource_id).strip()
            if not resource_id:
                return ("Error: resource_id cannot be empty.", [])

            logger.debug("Fetching metrics for resource_id: %s", resource_id)

            meta_lines_r: list[str] = []
            try:
                resource_meta = await datagouv_api_client.get_resource_metadata(
                    resource_id
                )
                resource_title = resource_meta.get("title", "Unknown")
                meta_lines_r.extend(
                    [
                        f"Resource Metrics: {resource_title}",
                        f"Resource ID: {resource_id}",
                        "",
                    ]
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not fetch resource metadata: %s", e)
                meta_lines_r.extend(
                    [
                        "Resource Metrics",
                        f"Resource ID: {resource_id}",
                        "",
                    ]
                )

            try:
                logger.debug(
                    "Calling metrics_api_client.get_metrics with resource_id: %s",
                    resource_id,
                )
                metrics_r = await metrics_api_client.get_metrics(
                    "resources", resource_id, limit=limit
                )
                if not metrics_r:
                    panels.append(
                        _MetricsPanel(
                            kind="resource",
                            metadata_lines=meta_lines_r,
                            rows=[],
                            empty_message="No metrics available for this resource.",
                        )
                    )
                else:
                    rrows: list[dict[str, Any]] = []
                    for entry in metrics_r:
                        rrows.append(
                            {
                                "month": entry.get("metric_month", "Unknown"),
                                "downloads": entry.get("monthly_download_resource", 0)
                                or 0,
                            }
                        )
                    panels.append(
                        _MetricsPanel(
                            kind="resource",
                            metadata_lines=meta_lines_r,
                            rows=rrows,
                        )
                    )
            except Exception as e:  # noqa: BLE001
                logger.error("Error fetching resource metrics: %s", e)
                panels.append(
                    _MetricsPanel(
                        kind="resource",
                        metadata_lines=meta_lines_r,
                        rows=[],
                        fetch_error=f"Error fetching resource metrics: {str(e)}",
                    )
                )

        return _metrics_panels_to_text(panels), panels
    except Exception as e:  # noqa: BLE001
        logger.exception("Unexpected error in get_metrics")
        return f"Error: {str(e)}", []


def register_get_metrics_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get usage metrics",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_metrics(
        dataset_id: str | None = None,
        resource_id: str | None = None,
        limit: int = 12,
    ) -> str:
        """
        Get usage metrics (visits, downloads) for a dataset or resource.

        Returns monthly statistics sorted by most recent first.
        At least one of dataset_id or resource_id must be provided.
        Note: Only available in production environment (not demo).
        """
        text, _panels = await _run_metrics_core(dataset_id, resource_id, limit)
        return text


def register_get_metrics_visual_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get usage metrics (visual)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def get_metrics_visual(
        dataset_id: str | None = None,
        resource_id: str | None = None,
        limit: int = 12,
    ) -> ToolResult:
        """
        Same data as get_metrics with an interactive chart and sortable table.

        Plain-text summary is always included for the model; the UI is optional for hosts.
        """
        text, panels = await _run_metrics_core(dataset_id, resource_id, limit)
        if not panels:
            return ToolResult(content=text, structured_content=None)
        return ToolResult(
            content=text, structured_content=_build_metrics_prefab(panels)
        )
