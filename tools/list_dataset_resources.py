import logging

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client

logger = logging.getLogger("datagouv_mcp")


def register_list_dataset_resources_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def list_dataset_resources(dataset_id: str) -> str:
        """
        List all resources (files) in a dataset with their metadata.

        Returns resource ID, title, format, size, and URL for each file.
        Next step: use query_resource_data for CSV/XLSX files,
        or download_and_parse_resource for other formats (JSON, JSONL) or large datasets.
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
            async with httpx.AsyncClient() as session:
                for i, (resource_id, resource_title) in enumerate(resources, 1):
                    content_parts.append(f"{i}. {resource_title or 'Untitled'}")
                    content_parts.append(f"   Resource ID: {resource_id}")

                    try:
                        resource_data = await datagouv_api_client.get_resource_details(
                            resource_id, session=session
                        )
                        resource = resource_data.get("resource", {})

                        if resource.get("format"):
                            content_parts.append(f"   Format: {resource.get('format')}")
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
                                content_parts.append(f"   Size: {size_str}")
                        if resource.get("mime"):
                            content_parts.append(
                                f"   MIME type: {resource.get('mime')}"
                            )
                        if resource.get("type"):
                            content_parts.append(f"   Type: {resource.get('type')}")
                        if resource.get("url"):
                            content_parts.append(f"   URL: {resource.get('url')}")
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            f"Could not fetch details for resource {resource_id}: {e}"
                        )

                    content_parts.append("")

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
