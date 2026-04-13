import logging

from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from tools.search_datasets import clean_search_query

logger = logging.getLogger(MAIN_LOGGER_NAME)


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
        List or search organizations (publishers) on data.gouv.fr via API v1.

        Use a short, specific search string when filtering by keywords: the API uses
        AND-style matching on tokens, so generic words may return no rows (same idea
        as dataset search).

        Optional sort values include: name, datasets, reuses, followers, views,
        created, last_modified, and the same names prefixed with '-' for descending
        order (e.g. -datasets).

        Optional badge filter (exact): public-service, certified, association,
        company, local-authority.

        Leave query empty to browse the catalog with pagination; combine with sort
        or badge to narrow results.
        """
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

        if not orgs:
            label = f"query '{query}'" if query else "current filters"
            return f"No organizations found for {label}"

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
        filter_desc = (
            ", ".join(filter_bits) if filter_bits else "browse (no text query)"
        )

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
