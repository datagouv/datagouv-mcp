import os
import sys

import aiohttp
import uvicorn
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, tabular_api_client

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
            f"Note: The API key must be valid for {expected_host}. Set DATAGOUV_ENV to switch environments."
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
                f"Environments use different API keys, so adjust DATAGOUV_ENV or pick a key from https://{expected_host}/fr/account/."
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


@mcp.tool()
async def query_dataset_data(
    question: str,
    dataset_id: str | None = None,
    dataset_query: str | None = None,
    limit_per_resource: int = 100,
) -> str:
    """
    Query data from a dataset by exploring its resources via the Tabular API.

    This tool finds a dataset (by ID or by searching), retrieves its resources, and uses
    the data.gouv.fr Tabular API to access tabular content directly (no local database required).

    Args:
        question: The question or description of what data you're looking for
        dataset_id: Optional dataset ID if you already know which dataset to query
        dataset_query: Optional search query to find the dataset if dataset_id is not provided
        limit_per_resource: Maximum number of rows to retrieve per resource table (default: 100)

    Returns:
        Formatted text with the data found, organized by resource
    """
    try:
        # Step 1: Find the dataset
        if dataset_id:
            # Use provided dataset ID
            dataset_result = await datagouv_api_client.get_resources_for_dataset(
                dataset_id
            )
            dataset = dataset_result.get("dataset", {})
            if not dataset.get("id"):
                return f"Error: Dataset with ID '{dataset_id}' not found."
        elif dataset_query:
            # Search for dataset
            search_result = await datagouv_api_client.search_datasets(
                query=dataset_query, page=1, page_size=1
            )
            datasets = search_result.get("data", [])
            if not datasets:
                return f"Error: No dataset found for query '{dataset_query}'."
            dataset_id = datasets[0].get("id")
            dataset_result = await datagouv_api_client.get_resources_for_dataset(
                dataset_id
            )
            dataset = dataset_result.get("dataset", {})
        else:
            return (
                "Error: Either 'dataset_id' or 'dataset_query' must be provided.\n"
                "Use dataset_id if you know the exact dataset ID, or dataset_query to search for a dataset."
            )

        dataset_title = dataset.get("title", "Unknown")
        dataset_id = dataset.get("id", dataset_id)

        # Step 2: Get resources for the dataset
        resources = dataset_result.get("resources", [])
        if not resources:
            return (
                f"Dataset '{dataset_title}' (ID: {dataset_id}) has no resources.\n"
                "No data tables are available to explore."
            )

        content_parts = [
            f"Exploring dataset: {dataset_title}",
            f"Dataset ID: {dataset_id}",
            f"Question: {question}",
            f"Found {len(resources)} resource(s) to explore\n",
        ]

        # Step 3 & 4: For each resource, fetch data via the Tabular API
        found_data = False
        for resource_id, resource_title in resources:
            content_parts.append(
                f"--- Resource: {resource_title or 'Untitled'} (ID: {resource_id}) ---"
            )

            try:
                page_size = max(1, min(limit_per_resource, 1000))
                tabular_data = await tabular_api_client.fetch_resource_data(
                    resource_id, page=1, page_size=page_size
                )
                rows = tabular_data.get("data", [])
                meta = tabular_data.get("meta", {})
                total_count = meta.get("total")
                page_info = meta.get("page")
                page_size_meta = meta.get("page_size")

                if not rows:
                    content_parts.append(
                        "  ⚠️  No rows available (resource may be empty or filtered)."
                    )
                    content_parts.append("")
                    continue

                found_data = True
                if total_count is not None:
                    content_parts.append(f"  Total rows (Tabular API): {total_count}")
                content_parts.append(f"  Retrieved: {len(rows)} row(s)")
                if page_info is not None and page_size_meta is not None:
                    content_parts.append(
                        f"  Page info: page {page_info} (page size {page_size_meta})"
                    )

                # Show column names
                if rows:
                    columns = list(rows[0].keys())
                    content_parts.append(f"  Columns: {', '.join(columns)}")

                # Show sample data (first few rows)
                content_parts.append("\n  Sample data (first 3 rows):")
                for i, row in enumerate(rows[:3], 1):
                    content_parts.append(f"    Row {i}:")
                    for key, value in row.items():
                        # Truncate long values
                        val_str = str(value)
                        if len(val_str) > 100:
                            val_str = val_str[:100] + "..."
                        content_parts.append(f"      {key}: {val_str}")

                if len(rows) > 3:
                    content_parts.append(
                        f"    ... ({len(rows) - 3} more row(s) available)"
                    )

                links = tabular_data.get("links", {})
                if links.get("next"):
                    content_parts.append(
                        "  More data available via Tabular API (next page link provided)."
                    )

            except tabular_api_client.ResourceNotAvailableError as e:
                content_parts.append(f"  ⚠️  {str(e)}")
            except aiohttp.ClientResponseError as e:
                content_parts.append(
                    f"  ❌ Tabular API error (HTTP {e.status}): {e.message}"
                )
            except Exception as e:
                content_parts.append(f"  ❌ Error exploring table: {str(e)}")

            content_parts.append("")

        if not found_data:
            content_parts.append(
                "⚠️  No data tables were found or accessible for the resources in this dataset."
            )

        return "\n".join(content_parts)

    except aiohttp.ClientResponseError as e:
        return f"Error: HTTP {e.status} - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


# Run with streamable HTTP transport
if __name__ == "__main__":
    port_str = os.getenv("MCP_PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(
            f"Error: Invalid MCP_PORT environment variable: {port_str}",
            file=sys.stderr,
        )
        sys.exit(1)
    uvicorn.run(mcp.streamable_http_app(), host="0.0.0.0", port=port, log_level="info")
