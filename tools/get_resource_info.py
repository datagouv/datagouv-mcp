import httpx
from mcp.server.fastmcp import FastMCP

from helpers import crawler_api_client, datagouv_api_client, env_config


def register_get_resource_info_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_resource_info(resource_id: str) -> str:
        """
        Get detailed information about a specific resource (file).

        Returns format, size, MIME type, URL, and checks Tabular API availability.
        Helps decide which tool to use: query_resource_data (if Tabular API available)
        or download_and_parse_resource (for large files or unsupported formats).
        """
        try:
            # Get full resource data from API v2
            resource_data = await datagouv_api_client.get_resource_details(resource_id)
            resource = resource_data.get("resource", {})
            if not resource.get("id"):
                return f"Error: Resource with ID '{resource_id}' not found."

            resource_title = resource.get("title") or resource.get("name") or "Unknown"

            content_parts = [
                f"Resource Information: {resource_title}",
                "",
                f"Resource ID: {resource_id}",
            ]

            if resource.get("format"):
                content_parts.append(f"Format: {resource.get('format')}")

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
                    content_parts.append(f"Size: {size_str}")

            if resource.get("mime"):
                content_parts.append(f"MIME type: {resource.get('mime')}")

            if resource.get("type"):
                content_parts.append(f"Type: {resource.get('type')}")

            if resource.get("url"):
                content_parts.append("")
                content_parts.append(f"URL: {resource.get('url')}")

            if resource.get("description"):
                content_parts.append("")
                content_parts.append(f"Description: {resource.get('description')}")

            # Dataset information
            dataset_id = resource_data.get("dataset_id")
            if dataset_id:
                content_parts.append("")
                content_parts.append(f"Dataset ID: {dataset_id}")
                try:
                    dataset_meta = await datagouv_api_client.get_dataset_metadata(
                        str(dataset_id)
                    )
                    if dataset_meta.get("title"):
                        content_parts.append(f"Dataset: {dataset_meta.get('title')}")
                except Exception:  # noqa: BLE001
                    pass

            # Check if resource is available via Tabular API
            content_parts.append("")
            content_parts.append("Tabular API availability:")
            try:
                # Check if resource is in the exceptions list (large files with special support)
                is_exception = await crawler_api_client.is_in_exceptions_list(
                    resource_id
                )

                # Try to get profile to check if it's tabular
                profile_url = f"{env_config.get_base_url('tabular_api')}resources/{resource_id}/profile/"
                async with httpx.AsyncClient() as session:
                    resp = await session.get(profile_url, timeout=10.0)
                    if resp.status_code == 200:
                        if is_exception:
                            content_parts.append(
                                "✅ Available via Tabular API (large file exception)"
                            )
                        else:
                            content_parts.append(
                                "✅ Available via Tabular API (can be queried)"
                            )
                    else:
                        content_parts.append(
                            "⚠️  Not available via Tabular API (may not be tabular data)"
                        )
            except Exception:  # noqa: BLE001
                content_parts.append("⚠️  Could not check Tabular API availability")

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
