import logging
from typing import Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from prefab_ui.app import PrefabApp
from prefab_ui.components import Column, DataTable, DataTableColumn

from helpers import datagouv_api_client
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL

logger = logging.getLogger(MAIN_LOGGER_NAME)


def clean_search_query(query: str) -> str:
    """
    Clean search query by removing generic stop words that are not typically
    present in dataset metadata but are often added by users.

    The API uses strict AND logic, so adding generic words like "données"
    that don't appear in metadata causes searches to return zero results.

    Args:
        query: Original search query

    Returns:
        Cleaned query with stop words removed
    """
    stop_words = {
        "données",
        "donnee",
        "donnees",
        "fichier",
        "fichiers",
        "fichier de",
        "fichiers de",
        "tableau",
        "tableaux",
        "csv",
        "excel",
        "xlsx",
        "json",
        "xml",
    }

    words = query.split()
    cleaned_words = [word for word in words if word.lower().strip() not in stop_words]

    cleaned_query = " ".join(cleaned_words)
    cleaned_query = " ".join(cleaned_query.split())

    if cleaned_query != query:
        logger.debug("Cleaned search query: '%s' -> '%s'", query, cleaned_query)

    return cleaned_query


async def _search_datasets_fetch(
    query: str,
    page: int,
    page_size: int,
    sort: str | None = None,
    last_update_range: str | None = None,
) -> dict[str, Any]:
    cleaned_query = clean_search_query(query)
    result = await datagouv_api_client.search_datasets(
        query=cleaned_query,
        page=page,
        page_size=page_size,
        sort=sort,
        last_update_range=last_update_range,
    )
    datasets = result.get("data", [])

    if not datasets and cleaned_query != query:
        logger.debug(
            "No results with cleaned query '%s', trying original query '%s'",
            cleaned_query,
            query,
        )
        result = await datagouv_api_client.search_datasets(
            query=query,
            page=page,
            page_size=page_size,
            sort=sort,
            last_update_range=last_update_range,
        )
        datasets = result.get("data", [])
        result["data"] = datasets

    return result


def _search_datasets_rows(datasets: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, ds in enumerate(datasets, 1):
        tags = ds.get("tags") or []
        tags_str = ", ".join(tags[:5]) if isinstance(tags, list) else str(tags)
        desc = ds.get("description_short") or ""
        if len(str(desc)) > 200:
            desc = str(desc)[:200] + "..."
        rows.append(
            {
                "#": i,
                "title": ds.get("title", "Untitled"),
                "id": str(ds.get("id", "")),
                "organization": str(ds.get("organization", "")),
                "resources_count": ds.get("resources_count", 0),
                "tags": tags_str,
                "url": str(ds.get("url", "")),
                "description_short": str(desc),
            }
        )
    return rows


def _search_datasets_text(query: str, result: dict[str, Any]) -> str:
    datasets = result.get("data", [])
    if not datasets:
        return f"No datasets found for query: '{query}'"

    content_parts = [
        f"Found {result.get('total', len(datasets))} dataset(s) for query: '{query}'",
        f"Page {result.get('page', 1)} of results:\n",
    ]
    for i, ds in enumerate(datasets, 1):
        content_parts.append(f"{i}. {ds.get('title', 'Untitled')}")
        content_parts.append(f"   ID: {ds.get('id')}")
        if ds.get("description_short"):
            desc = ds.get("description_short", "")[:200]
            content_parts.append(f"   Description: {desc}...")
        if ds.get("organization"):
            content_parts.append(f"   Organization: {ds.get('organization')}")
        if ds.get("tags"):
            tags = ", ".join(ds.get("tags", [])[:5])
            content_parts.append(f"   Tags: {tags}")
        content_parts.append(f"   Resources: {ds.get('resources_count', 0)}")
        content_parts.append(f"   URL: {ds.get('url')}")
        content_parts.append("")

    return "\n".join(content_parts)


async def _search_datasets_data(
    query: str,
    page: int,
    page_size: int,
    sort: str | None = None,
    last_update_range: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    result = await _search_datasets_fetch(
        query, page, page_size, sort, last_update_range
    )
    datasets = result.get("data", [])
    text = _search_datasets_text(query, result)
    if not datasets:
        return text, []
    return text, _search_datasets_rows(datasets)


def _search_datasets_prefab(rows: list[dict[str, Any]]) -> PrefabApp:
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
                        key="resources_count", header="Resources", sortable=True
                    ),
                    DataTableColumn(key="tags", header="Tags", sortable=False),
                    DataTableColumn(key="url", header="URL", sortable=False),
                    DataTableColumn(
                        key="description_short", header="Description", sortable=False
                    ),
                ],
                rows=rows,  # ty: ignore[invalid-argument-type]
                search=True,
            )
    return app


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_datasets(
        query: str,
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        last_update_range: str | None = None,
    ) -> str:
        """
        Search for datasets on data.gouv.fr by keywords.

        This is typically the first step in exploring data.gouv.fr.
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results).

        Use `sort` to order results. Accepted values: created, last_update,
        reuses, followers, views. Optionally prefixed with '-' for descending
        (e.g. -last_update). Use `last_update_range` to restrict
        results to recently updated datasets: last_30_days, last_12_months,
        last_3_years.

        Typical workflow: search_datasets → list_dataset_resources → query_resource_data.
        """
        text, _rows = await _search_datasets_data(
            query, page, page_size, sort, last_update_range
        )
        return text


def register_search_datasets_visual_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search datasets (visual)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def search_datasets_visual(
        query: str,
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        last_update_range: str | None = None,
    ) -> ToolResult:
        """
        Search for datasets on data.gouv.fr by keywords.

        This is typically the first step in exploring data.gouv.fr.
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results).

        Typical workflow: search_datasets → list_dataset_resources → query_resource_data.

        When the host supports app UI, includes a sortable, searchable table of results.
        Prefer this variant when the user should scan or compare many datasets in tabular form.
        """
        text, rows = await _search_datasets_data(
            query, page, page_size, sort, last_update_range
        )
        if not rows:
            return ToolResult(content=text, structured_content=None)
        return ToolResult(
            content=text,
            structured_content=_search_datasets_prefab(rows),
        )
