import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from helpers import datagouv_api_client, env_config


def register_get_dataset_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_dataset_info(dataset_id: str) -> str:
        """
        Get detailed metadata about a specific dataset.

        Returns title, description, organization, tags, resource count,
        creation/update dates, and license information.
        """
        try:
            # Get full dataset data from API v1 via helper
            data = await datagouv_api_client.get_dataset_details(dataset_id)

            content_parts = [f"Dataset Information: {data.get('title', 'Unknown')}", ""]

            if data.get("id"):
                content_parts.append(f"ID: {data.get('id')}")
            if data.get("slug"):
                content_parts.append(f"Slug: {data.get('slug')}")
                content_parts.append(
                    f"URL: {env_config.get_base_url('site')}datasets/{data.get('slug')}/"
                )

            if data.get("description_short"):
                content_parts.append("")
                content_parts.append(f"Description: {data.get('description_short')}")

            description = data.get("description")
            description_short = data.get("description_short")
            if description and description != description_short:
                content_parts.append("")
                content_parts.append(f"Full description: {description[:500]}...")

            if data.get("organization"):
                org = data.get("organization", {})
                if isinstance(org, dict):
                    content_parts.append("")
                    content_parts.append(f"Organization: {org.get('name', 'Unknown')}")
                    if org.get("id"):
                        content_parts.append(f"  Organization ID: {org.get('id')}")

            # Handle tags
            tags = []
            for tag in data.get("tags", []):
                if isinstance(tag, str):
                    tags.append(tag)
                elif isinstance(tag, dict):
                    tag_name = tag.get("name", "")
                    if tag_name:
                        tags.append(tag_name)
            if tags:
                content_parts.append("")
                content_parts.append(f"Tags: {', '.join(tags[:10])}")

            # Resources info
            resources = data.get("resources", [])
            content_parts.append("")
            content_parts.append(f"Resources: {len(resources)} file(s)")

            # Dates
            if data.get("created_at"):
                content_parts.append("")
                content_parts.append(f"Created: {data.get('created_at')}")
            if data.get("last_update"):
                content_parts.append(f"Last updated: {data.get('last_update')}")

            # License
            if data.get("license"):
                content_parts.append("")
                content_parts.append(f"License: {data.get('license')}")

            # Frequency
            if data.get("frequency"):
                content_parts.append(f"Update frequency: {data.get('frequency')}")

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"Error: Dataset with ID '{dataset_id}' not found."
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
