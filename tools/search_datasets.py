import logging

from mcp.server.fastmcp import FastMCP

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
        "dataset",
        "datasets",
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


HVD_DISCLAIMER = (
    "Disclaimer: This list only represents High-Value Datasets (HVDs) on data.gouv.fr. "
    "Many other datasets (70,000+) exist on the platform. Please specify a theme or "
    "keyword and use search_datasets for a broader query."
)


def format_dataset_entries(datasets: list[dict]) -> list[str]:
    content_parts: list[str] = []
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
    return content_parts


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search datasets",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_datasets(
        query: str = "",
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        last_update_range: str | None = None,
        tag: str | None = None,
    ) -> str:
        """
        Search for datasets on data.gouv.fr by keywords.

        This is typically the first step in exploring data.gouv.fr.
        Use short, specific queries (the API uses AND logic, so generic words
        like "données" or "fichier" may return zero results). If the user asks
        for datasets in general without specifying a theme, leave `query` empty
        or pass `tag="hvd"` (or call `list_high_value_datasets`) to return
        High-Value Datasets (HVDs) with a catalog disclaimer.

        Use `sort` to order results. Accepted values: created, last_update,
        reuses, followers, views. Optionally prefixed with '-' for descending
        (e.g. -last_update). Use `last_update_range` to restrict
        results to recently updated datasets: last_30_days, last_12_months,
        last_3_years.

        Typical workflow: search_datasets → list_dataset_resources → query_resource_data.
        """
        # Clean the query to remove generic stop words that break AND-based searches
        cleaned_query = clean_search_query(query)
        effective_tag = tag
        is_hvd_listing = effective_tag == "hvd" or (not cleaned_query and effective_tag is None)
        if is_hvd_listing and effective_tag is None:
            effective_tag = "hvd"

        # Try with cleaned query first
        result = await datagouv_api_client.search_datasets(
            query=cleaned_query,
            page=page,
            page_size=page_size,
            sort=sort,
            last_update_range=last_update_range,
            tag=effective_tag,
        )

        # Format the result as text content
        datasets = result.get("data", [])

        # Fallback: if cleaned query returns no results and it differs from original,
        # try with the original query
        if not datasets and cleaned_query != query and not is_hvd_listing:
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
                tag=effective_tag,
            )
            datasets = result.get("data", [])

        if not datasets:
            return f"No datasets found for query: '{query}'"

        content_parts: list[str] = []
        if is_hvd_listing:
            content_parts.append(HVD_DISCLAIMER)
            content_parts.append("")
        content_parts.extend(
            [
                f"Found {result.get('total', len(datasets))} dataset(s) for query: '{query}'",
                f"Page {result.get('page', 1)} of results:\n",
            ]
        )
        content_parts.extend(format_dataset_entries(datasets))

        return "\n".join(content_parts)
