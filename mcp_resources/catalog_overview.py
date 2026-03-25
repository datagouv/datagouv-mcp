from mcp.server.fastmcp import FastMCP

from helpers import env_config

CATALOG_OVERVIEW_URI = "datagouv://catalog-overview"


def _build_catalog_overview() -> str:
    site_url = env_config.get_base_url("site")
    data_env = env_config.get_base_url("datagouv_api")

    return "\n".join(
        [
            "# data.gouv.fr Catalog Overview",
            "",
            "This MCP server does not ship a fixed, preloaded list of datasets.",
            "It provides live read-only access to the current public catalog exposed by data.gouv.fr.",
            "",
            f"Current catalog site: {site_url}",
            f"Current API base: {data_env}",
            "",
            "When a user asks whether data is available for a topic, search first before concluding that the data is unavailable.",
            "",
            "Recommended discovery workflow:",
            "1. Use search_datasets for datasets and search_dataservices for APIs.",
            "2. Use get_dataset_info or get_dataservice_info to inspect the result.",
            "3. Use list_dataset_resources to enumerate files in a dataset.",
            "4. Use get_resource_info to inspect file metadata and raw URLs.",
            "5. Use query_resource_data to preview, filter, and sort tabular resources.",
            "6. Use get_metrics for usage metrics when you need visits or downloads.",
            "",
            "Available tools:",
            "- search_datasets: keyword search across the catalog.",
            "- get_dataset_info: detailed metadata for one dataset.",
            "- list_dataset_resources: list all resources for a dataset.",
            "- get_resource_info: inspect one resource and its access options.",
            "- query_resource_data: query CSV/XLSX-like tabular resources through the Tabular API.",
            "- search_dataservices: search third-party APIs listed on data.gouv.fr.",
            "- get_dataservice_info: inspect one dataservice.",
            "- get_dataservice_openapi_spec: fetch and summarize a dataservice OpenAPI spec.",
            "- get_metrics: retrieve dataset or resource usage metrics.",
            "",
            "Example questions this server should answer by searching first:",
            '- "Do you have datasets about housing prices in Paris?"',
            '- "Are there resources about EV charging stations?"',
            '- "What data is available for the Assemblee nationale?"',
        ]
    )


def register_catalog_overview_resource(mcp: FastMCP) -> None:
    @mcp.resource(
        CATALOG_OVERVIEW_URI,
        name="catalog_overview",
        title="Catalog Scope and Discovery Guide",
        description=(
            "Explains what this server can access on data.gouv.fr and how to "
            "discover datasets before claiming data is unavailable."
        ),
        mime_type="text/markdown",
    )
    def catalog_overview() -> str:
        return _build_catalog_overview()
