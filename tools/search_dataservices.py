import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, DataTable, DataTableColumn

from helpers import datagouv_api_client
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from tools.search_datasets import clean_search_query

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def _search_dataservices_fetch(
    query: str, page: int, page_size: int
) -> dict[str, Any]:
    cleaned_query = clean_search_query(query)

    result = await datagouv_api_client.search_dataservices(
        query=cleaned_query, page=page, page_size=page_size
    )

    dataservices = result.get("data", [])

    if not dataservices and cleaned_query != query:
        logger.debug(
            "No results with cleaned query '%s', trying original query '%s'",
            cleaned_query,
            query,
        )
        result = await datagouv_api_client.search_dataservices(
            query=query, page=page, page_size=page_size
        )
        dataservices = result.get("data", [])
        result["data"] = dataservices

    return result


def _search_dataservices_rows(dataservices: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, ds in enumerate(dataservices, 1):
        tags = ds.get("tags") or []
        tags_str = ", ".join(tags[:5]) if isinstance(tags, list) else str(tags)
        desc = ds.get("description") or ""
        if len(str(desc)) > 200:
            desc = str(desc)[:200] + "..."
        rows.append(
            {
                "#": i,
                "title": ds.get("title", "Untitled"),
                "id": str(ds.get("id", "")),
                "organization": str(ds.get("organization", "")),
                "base_api_url": str(ds.get("base_api_url", "")),
                "tags": tags_str,
                "url": str(ds.get("url", "")),
                "description": str(desc),
            }
        )
    return rows


def _search_dataservices_text(query: str, result: dict[str, Any]) -> str:
    dataservices = result.get("data", [])
    if not dataservices:
        return f"No third-party APIs found for query: '{query}'"

    content_parts = [
        f"Found {result.get('total', len(dataservices))} third-party API(s) for query: '{query}'",
        f"Page {result.get('page', 1)} of results:\n",
    ]
    for i, ds in enumerate(dataservices, 1):
        content_parts.append(f"{i}. {ds.get('title', 'Untitled')}")
        content_parts.append(f"   ID: {ds.get('id')}")
        if ds.get("description"):
            desc = ds.get("description", "")[:200]
            content_parts.append(f"   Description: {desc}...")
        if ds.get("organization"):
            content_parts.append(f"   Organization: {ds.get('organization')}")
        if ds.get("base_api_url"):
            content_parts.append(f"   Base API URL: {ds.get('base_api_url')}")
        if ds.get("tags"):
            tags = ", ".join(ds.get("tags", [])[:5])
            content_parts.append(f"   Tags: {tags}")
        content_parts.append(f"   URL: {ds.get('url')}")
        content_parts.append("")

    return "\n".join(content_parts)


async def _search_dataservices_data(
    query: str, page: int, page_size: int
) -> tuple[str, list[dict[str, Any]]]:
    result = await _search_dataservices_fetch(query, page, page_size)
    dataservices = result.get("data", [])
    text = _search_dataservices_text(query, result)
    if not dataservices:
        return text, []
    return text, _search_dataservices_rows(dataservices)


def _search_dataservices_prefab(rows: list[dict[str, Any]]) -> PrefabApp:
    with PrefabApp() as app:
        with Column(gap=4):
            DataTable(
                columns=[
                    DataTableColumn(key="#", header="#", sortable=True),
                    DataTableColumn(key="title", header="Title", sortable=True),
                    DataTableColumn(key="id", header="ID", sortable=True),
                    DataTableColumn(
                        key="organization", header="Organization", sortable=True
                    ),
                    DataTableColumn(
                        key="base_api_url", header="Base API URL", sortable=False
                    ),
                    DataTableColumn(key="tags", header="Tags", sortable=False),
                    DataTableColumn(key="url", header="URL", sortable=False),
                    DataTableColumn(
                        key="description", header="Description", sortable=False
                    ),
                ],
                rows=rows,  # ty: ignore[invalid-argument-type]
                search=True,
            )
    return app


def register_search_dataservices_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search third-party APIs",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_dataservices(
        query: str, page: int = 1, page_size: int = 20
    ) -> str:
        """
        Search for third-party APIs (dataservices) on data.gouv.fr by keywords.

        Third-party APIs (or dataservices) are APIs registered in the data.gouv.fr catalog
        that provide programmatic access to data (unlike datasets which are static files).
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results).

        Typical workflow: search_dataservices → get_dataservice_info →
        get_dataservice_openapi_spec → call the API using base_api_url per spec.
        """
        text, _rows = await _search_dataservices_data(query, page, page_size)
        return text


def register_search_dataservices_interactive_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search third-party APIs (interactive)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def search_dataservices_interactive(
        query: str, page: int = 1, page_size: int = 20
    ) -> ToolResult:
        """
        Search for third-party APIs (dataservices) on data.gouv.fr by keywords.

        Third-party APIs (or dataservices) are APIs registered in the data.gouv.fr catalog
        that provide programmatic access to data (unlike datasets which are static files).
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results).

        Typical workflow: search_dataservices → get_dataservice_info →
        get_dataservice_openapi_spec → call the API using base_api_url per spec.

        When the host supports app UI, includes a sortable, searchable table of results.
        Prefer this variant when the user should scan or compare many APIs in tabular form.
        """
        text, rows = await _search_dataservices_data(query, page, page_size)
        if not rows:
            return ToolResult(content=text, structured_content=None)
        return ToolResult(
            content=text,
            structured_content=_search_dataservices_prefab(rows),
        )
