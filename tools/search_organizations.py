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


async def _search_organizations_fetch(
    query: str = "",
    page: int = 1,
    page_size: int = 20,
    sort: str | None = None,
    badge: str | None = None,
    name: str | None = None,
    business_number_id: str | None = None,
) -> dict[str, Any]:
    cleaned_query = clean_search_query(query) if query else ""

    result = await datagouv_api_client.search_organizations(
        query=cleaned_query,
        page=page,
        page_size=page_size,
        sort=sort,
        badge=badge,
        name=name,
        business_number_id=business_number_id,
    )
    orgs = result.get("data", [])

    if not orgs and cleaned_query != query and query:
        logger.debug(
            "No org results with cleaned query '%s', trying original '%s'",
            cleaned_query,
            query,
        )
        result = await datagouv_api_client.search_organizations(
            query=query,
            page=page,
            page_size=page_size,
            sort=sort,
            badge=badge,
            name=name,
            business_number_id=business_number_id,
        )
        orgs = result.get("data", [])
        result["data"] = orgs

    return result


def _filter_desc(
    query: str,
    badge: str | None,
    name: str | None,
    business_number_id: str | None,
    sort: str | None,
) -> str:
    filter_bits: list[str] = []
    if query:
        filter_bits.append(f"query '{query}'")
    if badge:
        filter_bits.append(f"badge={badge}")
    if name:
        filter_bits.append(f"name={name}")
    if business_number_id:
        filter_bits.append(f"business_number_id={business_number_id}")
    if sort:
        filter_bits.append(f"sort={sort}")
    return ", ".join(filter_bits) if filter_bits else "browse (no text query)"


def _search_organizations_rows(orgs: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, org in enumerate(orgs, 1):
        title = org.get("name") or "Untitled"
        if org.get("acronym"):
            title = f"{title} ({org['acronym']})"
        metrics = org.get("metrics")
        metrics_str = ""
        if isinstance(metrics, dict):
            metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        badges = org.get("badges")
        badges_str = (
            ", ".join(badges) if isinstance(badges, list) else str(badges or "")
        )
        rows.append(
            {
                "#": i,
                "title": title,
                "id": str(org.get("id", "")),
                "slug": str(org.get("slug", "")),
                "badges": badges_str,
                "metrics": metrics_str,
                "url": str(org.get("url", "")),
                "profile_url": str(org.get("profile_url", "")),
            }
        )
    return rows


def _search_organizations_text(
    query: str,
    result: dict[str, Any],
    badge: str | None,
    name: str | None,
    business_number_id: str | None,
    sort: str | None,
) -> str:
    orgs = result.get("data", [])
    if not orgs:
        label = f"query '{query}'" if query else "current filters"
        return f"No organizations found for {label}"

    filter_desc = _filter_desc(query, badge, name, business_number_id, sort)
    content_parts = [
        f"Found {result.get('total', len(orgs))} organization(s) ({filter_desc})",
        f"Page {result.get('page', 1)} of results:\n",
    ]
    for i, org in enumerate(orgs, 1):
        title = org.get("name") or "Untitled"
        if org.get("acronym"):
            title = f"{title} ({org['acronym']})"
        content_parts.append(f"{i}. {title}")
        content_parts.append(f"   ID: {org.get('id')}")
        if org.get("slug"):
            content_parts.append(f"   Slug: {org.get('slug')}")
        if org.get("badges"):
            content_parts.append(f"   Badges: {', '.join(org['badges'])}")
        metrics = org.get("metrics")
        if metrics:
            parts = [f"{k}={v}" for k, v in metrics.items()]
            content_parts.append(f"   Metrics: {', '.join(parts)}")
        content_parts.append(f"   URL: {org.get('url')}")
        if org.get("profile_url") and org.get("profile_url") != org.get("url"):
            content_parts.append(f"   Profile: {org.get('profile_url')}")
        content_parts.append("")

    return "\n".join(content_parts)


async def _search_organizations_data(
    query: str = "",
    page: int = 1,
    page_size: int = 20,
    sort: str | None = None,
    badge: str | None = None,
    name: str | None = None,
    business_number_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    result = await _search_organizations_fetch(
        query, page, page_size, sort, badge, name, business_number_id
    )
    orgs = result.get("data", [])
    text = _search_organizations_text(
        query, result, badge, name, business_number_id, sort
    )
    if not orgs:
        return text, []
    return text, _search_organizations_rows(orgs)


def _search_organizations_prefab(rows: list[dict[str, Any]]) -> PrefabApp:
    with PrefabApp() as app:
        with Column(gap=4):
            DataTable(
                columns=[
                    DataTableColumn(key="#", header="#", sortable=True),
                    DataTableColumn(key="title", header="Name", sortable=True),
                    DataTableColumn(key="id", header="ID", sortable=True),
                    DataTableColumn(key="slug", header="Slug", sortable=True),
                    DataTableColumn(key="badges", header="Badges", sortable=False),
                    DataTableColumn(key="metrics", header="Metrics", sortable=False),
                    DataTableColumn(key="url", header="URL", sortable=False),
                    DataTableColumn(
                        key="profile_url", header="Profile", sortable=False
                    ),
                ],
                rows=rows,
                search=True,
            )
    return app


def register_search_organizations_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search organizations",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_organizations(
        query: str = "",
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        badge: str | None = None,
        name: str | None = None,
        business_number_id: str | None = None,
    ) -> str:
        """
        Find publishing organizations on data.gouv.fr (who publishes datasets and
        reuses).

        Pass a short `query` with distinctive words (acronym, ministry name, city,
        \"INSEE\", etc.). Generic or very broad terms often return large result sets;
        combine with `page` / `page_size` or add `badge` / `name` / `business_number_id`
        when you need a narrow list.

        Leave `query` empty to list organizations with pagination (same as browsing
        the catalog). Use `sort` to order results (e.g. name, datasets, reuses,
        followers, views, created, last_modified, or the same with a leading '-' for
        descending, such as -datasets).

        `badge` filters by publisher type: public-service, certified, association,
        company, local-authority.

        The reply includes how many organizations matched, the current page, and for
        each hit: name (and acronym if any), id, slug, badges, optional usage
        metrics, and links to the organization page.
        """
        text, _rows = await _search_organizations_data(
            query,
            page,
            page_size,
            sort,
            badge,
            name,
            business_number_id,
        )
        return text


def register_search_organizations_visual_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search organizations (visual)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
        app=True,
    )
    @log_tool
    async def search_organizations_visual(
        query: str = "",
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        badge: str | None = None,
        name: str | None = None,
        business_number_id: str | None = None,
    ) -> ToolResult:
        """
        Same as search_organizations with a sortable, searchable results table.
        """
        text, rows = await _search_organizations_data(
            query,
            page,
            page_size,
            sort,
            badge,
            name,
            business_number_id,
        )
        if not rows:
            return ToolResult(content=text, structured_content=None)
        return ToolResult(
            content=text,
            structured_content=_search_organizations_prefab(rows),
        )
