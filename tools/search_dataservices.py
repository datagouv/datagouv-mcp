import logging

from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client
from tools.search_datasets import clean_search_query

logger = logging.getLogger("datagouv_mcp")


def register_search_dataservices_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_dataservices(
        query: str, page: int = 1, page_size: int = 20
    ) -> str:
        """
        Search for dataservices (external third-party APIs) on data.gouv.fr by keywords.

        Dataservices are third-party APIs registered in the data.gouv.fr catalog
        that provide programmatic access to data (unlike datasets which are static files).
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results).

        Typical workflow: search_dataservices → get_dataservice_info →
        get_dataservice_openapi_spec → call the API using base_api_url per spec.
        """
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

        if not dataservices:
            return f"No dataservices found for query: '{query}'"

        content_parts = [
            f"Found {result.get('total', len(dataservices))} dataservice(s) for query: '{query}'",
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
