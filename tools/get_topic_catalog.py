import niquests
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, env_config
from helpers.logging import log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def register_get_topic_catalog_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Get topic catalog",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def get_topic_catalog(topic_id: str) -> str:
        """
        Get the contextualization catalog of a data.gouv.fr topic.

        Reads the topic's `extras.mcp.catalog_dataset_id` field and returns
        the associated catalog dataset, which documents the datasets of the
        topic and their column schemas.

        A topic that declares such a catalog is treated as a documented
        perimeter: query the catalog resources with `query_resource_data`
        to discover and select datasets before querying them.

        Typical workflow: search_topics → get_topic_catalog → query_resource_data.
        """
        try:
            topic = await datagouv_api_client.get_topic_details(topic_id)
        except niquests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                return f"Error: Topic '{topic_id}' not found."
            if status is not None:
                return f"Error: HTTP {status} - {str(e)}"
            return f"Error: {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"

        topic_name = topic.get("name") or topic_id
        topic_slug = topic.get("slug") or topic_id
        mcp_extras = (topic.get("extras") or {}).get("mcp") or {}
        catalog_dataset_id = mcp_extras.get("catalog_dataset_id")
        catalog_version = mcp_extras.get("version")

        header = [
            f"Topic: {topic_name}",
            f"Slug: {topic_slug}",
        ]
        if topic.get("id"):
            header.append(f"ID: {topic.get('id')}")

        if not catalog_dataset_id:
            return "\n".join(
                header
                + [
                    "",
                    "No contextualization catalog is declared for this topic "
                    "(no extras.mcp.catalog_dataset_id).",
                    "Use list_topic_elements to browse its datasets directly.",
                ]
            )

        try:
            dataset = await datagouv_api_client.get_dataset_details(catalog_dataset_id)
        except niquests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            detail = f"HTTP {status}" if status is not None else str(e)
            return "\n".join(
                header
                + [
                    "",
                    f"Contextualization catalog declared: dataset '{catalog_dataset_id}'",
                    f"Error: the catalog dataset could not be retrieved ({detail}).",
                    "Use list_topic_elements to browse the topic datasets directly.",
                ]
            )
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"

        site_base = env_config.get_base_url("site").rstrip("/")
        content_parts = header + [
            "",
            f"Contextualization catalog: {dataset.get('title', 'Untitled')}",
            f"Catalog dataset ID: {catalog_dataset_id}",
        ]
        if catalog_version:
            content_parts.append(f"Convention version: {catalog_version}")
        content_parts.append(f"URL: {site_base}/datasets/{catalog_dataset_id}/")

        resources = dataset.get("resources", [])
        content_parts.append("")
        content_parts.append(f"Catalog resources: {len(resources)} file(s)")
        for i, r in enumerate(resources, 1):
            content_parts.append(f"{i}. {r.get('title') or 'Untitled'}")
            if r.get("id"):
                content_parts.append(f"   Resource ID: {r.get('id')}")
            if r.get("format"):
                content_parts.append(f"   Format: {r.get('format')}")
            if r.get("type"):
                content_parts.append(f"   Type: {r.get('type')}")
            if r.get("url"):
                content_parts.append(f"   URL: {r.get('url')}")
        if resources:
            content_parts.append("")
            content_parts.append(
                "Use query_resource_data with a Resource ID above to read the catalog."
            )

        return "\n".join(content_parts)
