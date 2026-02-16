import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from helpers import datagouv_api_client

logger = logging.getLogger("datagouv_mcp")


def _summarize_parameters(params: list[dict[str, Any]]) -> str:
    """Summarize OpenAPI parameters into a compact string."""
    parts = []
    for p in params:
        name = p.get("name", "?")
        location = p.get("in", "")
        required = p.get("required", False)
        schema = p.get("schema", {})
        ptype = schema.get("type", "")
        marker = " (required)" if required else ""
        parts.append(f"      - {name} [{location}, {ptype}]{marker}")
    return "\n".join(parts)


def _summarize_spec(spec: dict[str, Any]) -> str:
    """
    Summarize an OpenAPI spec into a concise text representation.
    Includes: API info, servers, and endpoints with parameters.
    Skips: response schemas, model definitions, examples.
    """
    parts: list[str] = []

    # API info
    info = spec.get("info", {})
    if info.get("title"):
        parts.append(f"API: {info['title']}")
    if info.get("version"):
        parts.append(f"Version: {info['version']}")
    if info.get("description"):
        desc = info["description"][:300]
        parts.append(f"Description: {desc}...")

    # Servers / base URL
    servers = spec.get("servers", [])
    if servers:
        parts.append("")
        parts.append("Servers:")
        for s in servers[:3]:
            url = s.get("url", "")
            desc = s.get("description", "")
            parts.append(f"  - {url}" + (f" ({desc})" if desc else ""))

    # OpenAPI 2.0 (Swagger) base URL
    if spec.get("host"):
        scheme = (spec.get("schemes") or ["https"])[0]
        base_path = spec.get("basePath", "")
        parts.append(f"\nBase URL: {scheme}://{spec['host']}{base_path}")

    # Endpoints
    paths = spec.get("paths", {})
    if paths:
        parts.append("")
        parts.append(f"Endpoints ({len(paths)} paths):")
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, details in methods.items():
                if method.startswith("x-") or method == "parameters":
                    continue
                if not isinstance(details, dict):
                    continue
                summary = details.get("summary", details.get("description", ""))
                if summary:
                    summary = summary.split("\n")[0][:120]
                parts.append(f"  {method.upper()} {path}")
                if summary:
                    parts.append(f"    {summary}")
                params = details.get("parameters", [])
                if params:
                    parts.append(_summarize_parameters(params))

    return "\n".join(parts)


def register_get_dataservice_openapi_spec_tool(mcp: FastMCP) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_dataservice_openapi_spec(dataservice_id: str) -> str:
        """
        Fetch and summarize the OpenAPI/Swagger spec for a dataservice (external third-party API).

        Retrieves the machine_documentation_url from the dataservice metadata,
        fetches the spec, and returns a summary of available endpoints with
        their parameters. Use this to understand how to call the API.

        Typical workflow: search_dataservices → get_dataservice_info →
        get_dataservice_openapi_spec → call the API using base_api_url per spec.
        """
        try:
            data = await datagouv_api_client.get_dataservice_details(dataservice_id)

            doc_url = data.get("machine_documentation_url")
            base_api_url = data.get("base_api_url")
            title = data.get("title", "Unknown")

            if not doc_url:
                msg = f"Dataservice '{title}' has no machine_documentation_url."
                if base_api_url:
                    msg += f" Base API URL is: {base_api_url}"
                return msg

            spec = await datagouv_api_client.fetch_openapi_spec(doc_url)
            summary = _summarize_spec(spec)

            content_parts = [
                f"OpenAPI spec for: {title}",
                f"Source: {doc_url}",
            ]
            if base_api_url:
                content_parts.append(f"Base API URL: {base_api_url}")
            content_parts.append("")
            content_parts.append(summary)

            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"Error: Dataservice with ID '{dataservice_id}' not found."
            return f"Error: HTTP {e.response.status_code} - {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error fetching OpenAPI spec: {str(e)}"
