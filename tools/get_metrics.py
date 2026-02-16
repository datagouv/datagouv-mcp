import logging
import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from helpers import datagouv_api_client, metrics_api_client

logger = logging.getLogger("datagouv_mcp")


def register_get_metrics_tool(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
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
        # Check if we're in demo environment
        current_env: str = os.getenv("DATAGOUV_ENV", "prod").strip().lower()
        if current_env == "demo":
            return (
                "Error: The Metrics API is not available in the demo environment.\n"
                "The Metrics API only exists in production. Please set DATAGOUV_ENV=prod "
                "to use this tool, or switch to production environment to access metrics data."
            )

        if not dataset_id and not resource_id:
            return "Error: At least one of dataset_id or resource_id must be provided."

        content_parts: list[str] = []
        limit = max(1, min(limit, 100))

        try:
            if dataset_id:
                # Clean and validate dataset_id
                dataset_id = str(dataset_id).strip()
                if not dataset_id:
                    return "Error: dataset_id cannot be empty."

                logger.debug(f"Fetching metrics for dataset_id: {dataset_id}")

                # Get dataset metadata for context
                try:
                    dataset_meta = await datagouv_api_client.get_dataset_metadata(
                        dataset_id
                    )
                    dataset_title = dataset_meta.get("title", "Unknown")
                    content_parts.append(f"Dataset Metrics: {dataset_title}")
                    content_parts.append(f"Dataset ID: {dataset_id}")
                    content_parts.append("")
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Could not fetch dataset metadata: {e}")
                    content_parts.append("Dataset Metrics")
                    content_parts.append(f"Dataset ID: {dataset_id}")
                    content_parts.append("")

                # Get dataset metrics
                try:
                    logger.debug(
                        f"Calling metrics_api_client.get_metrics with dataset_id: {dataset_id}"
                    )
                    metrics = await metrics_api_client.get_metrics(
                        "datasets", dataset_id, limit=limit
                    )
                    logger.debug(
                        f"Received {len(metrics) if metrics else 0} metric entries"
                    )

                    if not metrics:
                        content_parts.append("No metrics available for this dataset.")
                    else:
                        content_parts.append("Monthly Statistics:")
                        content_parts.append("-" * 60)
                        content_parts.append(
                            f"{'Month':<12} {'Visits':<15} {'Downloads':<15}"
                        )
                        content_parts.append("-" * 60)

                        total_visits = 0
                        total_downloads = 0
                        for entry in metrics:
                            month = entry.get("metric_month", "Unknown")
                            visits = entry.get("monthly_visit", 0)
                            downloads = entry.get("monthly_download_resource", 0)
                            total_visits += visits
                            total_downloads += downloads
                            content_parts.append(
                                f"{month:<12} {visits:<15,} {downloads:<15,}"
                            )

                        content_parts.append("-" * 60)
                        content_parts.append(
                            f"{'Total':<12} {total_visits:<15,} {total_downloads:<15,}"
                        )
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error fetching dataset metrics: {e}")
                    content_parts.append(f"Error fetching dataset metrics: {str(e)}")

                if resource_id:
                    content_parts.append("")
                    content_parts.append("")

            if resource_id:
                # Clean and validate resource_id
                resource_id = str(resource_id).strip()
                if not resource_id:
                    return "Error: resource_id cannot be empty."

                logger.debug(f"Fetching metrics for resource_id: {resource_id}")

                # Get resource metadata for context
                try:
                    resource_meta = await datagouv_api_client.get_resource_metadata(
                        resource_id
                    )
                    resource_title = resource_meta.get("title", "Unknown")
                    content_parts.append(f"Resource Metrics: {resource_title}")
                    content_parts.append(f"Resource ID: {resource_id}")
                    content_parts.append("")
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"Could not fetch resource metadata: {e}")
                    content_parts.append("Resource Metrics")
                    content_parts.append(f"Resource ID: {resource_id}")
                    content_parts.append("")

                # Get resource metrics
                try:
                    logger.debug(
                        f"Calling metrics_api_client.get_metrics with resource_id: {resource_id}"
                    )
                    metrics = await metrics_api_client.get_metrics(
                        "resources", resource_id, limit=limit
                    )
                    logger.debug(
                        f"Received {len(metrics) if metrics else 0} metric entries"
                    )

                    if not metrics:
                        content_parts.append("No metrics available for this resource.")
                    else:
                        content_parts.append("Monthly Statistics:")
                        content_parts.append("-" * 40)
                        content_parts.append(f"{'Month':<12} {'Downloads':<15}")
                        content_parts.append("-" * 40)

                        total_downloads = 0
                        for entry in metrics:
                            month = entry.get("metric_month", "Unknown")
                            downloads = entry.get("monthly_download_resource", 0)
                            total_downloads += downloads
                            content_parts.append(f"{month:<12} {downloads:<15,}")

                        content_parts.append("-" * 40)
                        content_parts.append(f"{'Total':<12} {total_downloads:<15,}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error fetching resource metrics: {e}")
                    content_parts.append(f"Error fetching resource metrics: {str(e)}")

            return "\n".join(content_parts)

        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error in get_metrics")
            return f"Error: {str(e)}"
