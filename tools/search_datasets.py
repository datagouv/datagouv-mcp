import logging

from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client

logger = logging.getLogger("datagouv_mcp")


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
    # Stop words that are generic and often not in dataset metadata
    # These are words users commonly add but that break AND-based searches
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

    # Split query into words, preserving spacing
    words = query.split()
    # Filter out stop words (case-insensitive)
    cleaned_words = [word for word in words if word.lower().strip() not in stop_words]

    # Rejoin words, preserving original spacing pattern
    cleaned_query = " ".join(cleaned_words)
    # Clean up multiple spaces
    cleaned_query = " ".join(cleaned_query.split())

    if cleaned_query != query:
        logger.debug("Cleaned search query: '%s' -> '%s'", query, cleaned_query)

    return cleaned_query


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_datasets(query: str, page: int = 1, page_size: int = 20) -> str:
        """
        Search for datasets on data.gouv.fr by keywords.

        This is typically the first step in exploring data.gouv.fr. Returns a list of
        datasets matching the search query with their metadata, including title,
        description, organization, tags, and resource count.

        After finding relevant datasets, use get_dataset_info to get more details, or
        list_dataset_resources to see what files are available in a dataset.

        Args:
            query: Search query string (searches in title, description, tags)
            page: Page number (default: 1)
            page_size: Number of results per page (default: 20, max: 100)

        Returns:
            Formatted text with dataset information, including dataset IDs for further queries
        """
        # Clean the query to remove generic stop words that break AND-based searches
        cleaned_query = clean_search_query(query)

        # Try with cleaned query first
        result = await datagouv_api_client.search_datasets(
            query=cleaned_query, page=page, page_size=page_size
        )

        # Format the result as text content
        datasets = result.get("data", [])

        # Fallback: if cleaned query returns no results and it differs from original,
        # try with the original query
        if not datasets and cleaned_query != query:
            logger.debug(
                "No results with cleaned query '%s', trying original query '%s'",
                cleaned_query,
                query,
            )
            result = await datagouv_api_client.search_datasets(
                query=query, page=page, page_size=page_size
            )
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
