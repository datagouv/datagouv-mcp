from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client
from helpers.logging import log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL
from tools.search_datasets import (
    HVD_DISCLAIMER,
    clean_search_query,
    format_dataset_entries,
)


def register_list_high_value_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="List High-Value Datasets (HVD)",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def list_high_value_datasets(
        query: str = "",
        page: int = 1,
        page_size: int = 20,
        sort: str | None = None,
        last_update_range: str | None = None,
    ) -> str:
        """
        List available High-Value Datasets (HVDs) from data.gouv.fr.

        Call this tool when the user asks what datasets are available in general
        without specifying a particular theme, or when they explicitly ask for
        High-Value Datasets (données de forte valeur / HVD).

        The response includes a disclaimer explaining that this list only
        represents High-Value Datasets and that over 70,000 other datasets exist
        on data.gouv.fr. Encourage the user to specify a theme and use
        `search_datasets` for a broader query.
        """
        cleaned_query = clean_search_query(query) if query else ""
        result = await datagouv_api_client.search_datasets(
            query=cleaned_query,
            page=page,
            page_size=page_size,
            sort=sort,
            last_update_range=last_update_range,
            tag="hvd",
        )
        datasets = result.get("data", [])

        if not datasets:
            label = f" for query: '{query}'" if query else ""
            return f"{HVD_DISCLAIMER}\n\nNo High-Value Datasets found{label}"

        header = (
            f"Found {result.get('total', len(datasets))} High-Value Dataset(s)"
            + (f" for query: '{query}'" if query else "")
        )
        content_parts = [
            HVD_DISCLAIMER,
            "",
            header,
            f"Page {result.get('page', 1)} of results:\n",
        ]
        content_parts.extend(format_dataset_entries(datasets))
        return "\n".join(content_parts)
