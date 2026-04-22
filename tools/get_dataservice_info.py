from typing import Any

import httpx
from fastmcp import FastMCP

from helpers import datagouv_api_client, env_config
from helpers.logging import log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def register_get_dataservice_info_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get third-party API info",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_dataservice_info(dataservice_id: str) -> str:
        """
        Get detailed metadata about a specific third-party API (dataservice).

        Returns title, description, organization, base_api_url,
        machine_documentation_url (OpenAPI/Swagger spec), license, and dates.

        To use a third-party API: (1) get its info here, (2) fetch the OpenAPI spec
        via get_dataservice_openapi_spec, (3) call base_api_url per spec.
        """
        try:
            data = await datagouv_api_client.get_dataservice_details(dataservice_id)

            content_parts = [
                f"Third-party API information: {data.get('title', 'Unknown')}",
                "",
            ]

            if data.get("id"):
                content_parts.append(f"ID: {data.get('id')}")
            content_parts.append(
                f"URL: {env_config.get_base_url('site')}dataservices/{data.get('id', '')}/"
            )

            if data.get("description"):
                content_parts.append("")
                desc = data.get("description", "")[:500]
                content_parts.append(f"Description: {desc}...")

            # Catalog resource fields for this third-party API (dataservice)
            content_parts.append("")
            if data.get("base_api_url"):
                content_parts.append(f"Base API URL: {data.get('base_api_url')}")
            if data.get("machine_documentation_url"):
                content_parts.append(
                    f"OpenAPI/Swagger spec: {data.get('machine_documentation_url')}"
                )

            if data.get("organization"):
                org = data.get("organization", {})
                if isinstance(org, dict):
                    content_parts.append("")
                    content_parts.append(f"Organization: {org.get('name', 'Unknown')}")
                    if org.get("id"):
                        content_parts.append(f"  Organization ID: {org.get('id')}")

            tags: list[str] = data.get("tags") or []
            if tags:
                content_parts.append("")
                content_parts.append(f"Tags: {', '.join(tags[:10])}")

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

            # Related datasets (API returns a link object, not a list)
            datasets: dict[str, Any] = data.get("datasets", {})
            if isinstance(datasets, dict) and datasets.get("total"):
                content_parts.append("")
                content_parts.append(f"Related datasets: {datasets['total']}")

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"Error: Third-party API not found (dataservice_id='{dataservice_id}')."
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"
