import os

import aiohttp
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client

# Create an MCP server
mcp = FastMCP("data.gouv.fr MCP server")


@mcp.tool()
async def search_datasets(query: str, page: int = 1, page_size: int = 20) -> str:
    """
    Search for datasets on data.gouv.fr by keywords.

    Returns a list of datasets matching the search query with their metadata,
    including title, description, organization, tags, and resource count.
    Use this to discover datasets before querying their data.

    Args:
        query: Search query string (searches in title, description, tags)
        page: Page number (default: 1)
        page_size: Number of results per page (default: 20, max: 100)

    Returns:
        Formatted text with dataset information
    """
    result = await datagouv_api_client.search_datasets(
        query=query, page=page, page_size=page_size
    )

    # Format the result as text content
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


@mcp.tool()
async def create_dataset(
    title: str,
    description: str,
    organization: str | None = None,
    private: bool = False,
    api_key: str | None = None,
) -> str:
    """
    Create a new dataset on data.gouv.fr.

    Requires a data.gouv.fr API key supplied by the MCP client via the `api_key` parameter.
    Configure your MCP client to pass the key automatically (e.g., Cursor's `config.apiKey`).

    By default, datasets created via the API are public. Set private=True to create a draft.

    Args:
        title: Dataset title
        description: Dataset description
        organization: Optional organization ID or slug
        private: If True, create as draft (private). Default: False (public)
        api_key: API key forwarded by the MCP client (required)

    Returns:
        Formatted text with created dataset information including ID, slug, and URL
    """
    # Get API key from parameter
    # The MCP client (e.g., Cursor) passes the API key directly as a parameter
    # when calling the tool, based on the client's MCP configuration (config.apiKey)
    final_api_key = api_key

    current_env = datagouv_api_client.get_current_environment()
    expected_host = "demo.data.gouv.fr" if current_env == "demo" else "www.data.gouv.fr"

    print(f"final_api_key: {final_api_key}")
    if not final_api_key:
        return (
            "Error: API key required. "
            "Provide it via the api_key parameter, or configure it in your MCP client settings (as 'apiKey' or 'api_key' in the client configuration). "
            f"Note: The API key must be valid for {expected_host}. Set DATAGOUV_API_ENV to switch environments."
        )

    try:
        result = await datagouv_api_client.create_dataset(
            title=title,
            description=description,
            api_key=final_api_key,
            organization=organization,
            private=private,
        )

        dataset_id = result.get("id")
        slug = result.get("slug")
        created_title = result.get("title", title)

        content_parts = [
            "✅ Dataset created successfully!",
            "",
            f"Title: {created_title}",
            f"ID: {dataset_id}",
        ]

        if slug:
            content_parts.append(f"Slug: {slug}")
            content_parts.append(
                f"URL: {datagouv_api_client.frontend_base_url()}datasets/{slug}/"
            )

        if private:
            content_parts.append("")
            content_parts.append("⚠️  Note: Dataset created as draft (private).")

        content_parts.append("")
        content_parts.append(
            "You can now add resources to this dataset using the create_resource tool."
        )

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        error_message = str(e)
        if e.status == 401:
            return (
                f"Error: Authentication failed (401). Please check your API key.\n"
                f"Details: {error_message}\n"
                f"Note: The API key must be valid for {expected_host}. "
                f"Environments use different API keys, so adjust DATAGOUV_API_ENV or pick a key from https://{expected_host}/fr/account/."
            )
        elif e.status == 400:
            return f"Error: Invalid request (400). {error_message}"
        elif e.status == 403:
            return (
                f"Error: Forbidden (403). You may not have permission to create datasets.\n"
                f"Details: {error_message}"
            )
        else:
            return f"Error: Failed to create dataset (HTTP {e.status}). {error_message}"
    except Exception as e:
        return f"Error: Failed to create dataset. {str(e)}"


@mcp.resource(
    "datagouv://resources",
    name="Available Resources",
    title="Available Resource Templates",
    description="List of available resource URI templates for accessing data.gouv.fr datasets and resources",
)
def list_available_resources() -> str:
    """
    List available resource templates on data.gouv.fr.

    This resource provides information about the available resource URI templates
    that can be used to access datasets and resources on data.gouv.fr.
    """
    return """Available resource templates:

1. datagouv://dataset/{dataset_id}
   Get dataset metadata and list all its resources.
   Example: datagouv://dataset/53ba5b91a3a729219b7beae9

2. datagouv://resource/{resource_id}
   Get resource metadata including its dataset information.
   Example: datagouv://resource/580f2c63-8d22-490a-9ad3-eaef71edcae3

Workflow:
1. Use search_datasets tool to find datasets
2. Use datagouv://dataset/{dataset_id} to explore a dataset's resources
3. Use datagouv://resource/{resource_id} to get details about a specific resource
"""


@mcp.resource(
    "datagouv://dataset/{dataset_id}",
    name="Dataset Resource",
    title="Dataset Metadata and Resources",
    description="Get dataset metadata and list all its resources. Use after finding a dataset with search_datasets.",
)
async def get_dataset_resource(dataset_id: str) -> str:
    """
    Get dataset metadata and list all its resources.

    This resource provides information about a specific dataset on data.gouv.fr,
    including its title, description, and all available resources with their IDs and titles.
    Use this after finding a dataset with search_datasets to explore its resources.

    Args:
        dataset_id: The ID of the dataset to retrieve
    """
    result = await datagouv_api_client.get_resources_for_dataset(dataset_id)

    dataset = result.get("dataset", {})
    resources = result.get("resources", [])

    content_parts = [
        f"Dataset: {dataset.get('title', 'Untitled')}",
        f"ID: {dataset.get('id')}",
        "",
    ]

    if dataset.get("description_short"):
        content_parts.append(f"Description: {dataset.get('description_short')}")
        content_parts.append("")

    if dataset.get("description"):
        desc = dataset.get("description", "")[:500]
        content_parts.append(f"Full description: {desc}...")
        content_parts.append("")

    content_parts.append(f"Resources ({len(resources)}):")
    content_parts.append("")

    if not resources:
        content_parts.append("  No resources available for this dataset.")
    else:
        for i, (res_id, res_title) in enumerate(resources, 1):
            content_parts.append(f"  {i}. {res_title or 'Untitled'}")
            content_parts.append(f"     Resource ID: {res_id}")
            content_parts.append(f"     URI: datagouv://resource/{res_id}")
            content_parts.append("")

    return "\n".join(content_parts)


@mcp.resource(
    "datagouv://resource/{resource_id}",
    name="Resource Metadata",
    title="Resource Information",
    description="Get resource metadata including its dataset information. Use to get details about a resource before querying its data.",
)
async def get_resource_resource(resource_id: str) -> str:
    """
    Get resource metadata including its dataset information.

    This resource provides information about a specific resource on data.gouv.fr,
    including its title, description, and the dataset it belongs to.
    Use this to get details about a resource before querying its data.

    Args:
        resource_id: The ID of the resource to retrieve
    """
    result = await datagouv_api_client.get_resource_and_dataset_metadata(resource_id)

    resource = result.get("resource", {})
    dataset = result.get("dataset", {})

    content_parts = [
        f"Resource: {resource.get('title', 'Untitled')}",
        f"Resource ID: {resource.get('id')}",
        "",
    ]

    if resource.get("description"):
        content_parts.append(f"Description: {resource.get('description')}")
        content_parts.append("")

    if dataset:
        content_parts.append(f"Dataset: {dataset.get('title', 'Untitled')}")
        content_parts.append(f"Dataset ID: {dataset.get('id')}")
        content_parts.append(f"Dataset URI: datagouv://dataset/{dataset.get('id')}")
        if dataset.get("description_short"):
            content_parts.append(
                f"Dataset description: {dataset.get('description_short')}"
            )
        content_parts.append("")

    return "\n".join(content_parts)


# Run with streamable HTTP transport
if __name__ == "__main__":
    import os
    import sys

    # Get port from environment variable; default to 8000 for local dev
    port_str = os.getenv("MCP_PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(
            f"Error: Invalid MCP_PORT environment variable: {port_str}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Use uvicorn to run the Starlette app with custom port
    import uvicorn

    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port, log_level="info")
