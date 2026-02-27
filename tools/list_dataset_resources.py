import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client
from helpers.formatting import format_file_size


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

            for i, resource in enumerate(resources, 1):
                resource_id = resource.get("id")
                resource_title = resource.get("title")
                content_parts.append(f"{i}. {resource_title or 'Untitled'}")
                content_parts.append(f"   Resource ID: {resource_id}")

                if resource.get("format"):
                    content_parts.append(f"   Format: {resource.get('format')}")

                size = resource.get("filesize")
                if isinstance(size, int):
                    content_parts.append(f"   Size: {format_file_size(size)}")

                if resource.get("mime"):
                    content_parts.append(f"   MIME type: {resource.get('mime')}")
                if resource.get("type"):
                    content_parts.append(f"   Type: {resource.get('type')}")
                if resource.get("url"):
                    content_parts.append(f"   URL: {resource.get('url')}")

                content_parts.append("")

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
