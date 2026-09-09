import niquests
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, env_config
from helpers.logging import log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


def register_search_topics_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="Search topics",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def search_topics(
        query: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """
        Search thematic topics on data.gouv.fr by keywords.

        A topic groups datasets (and other objects) around a theme or a
        publisher's perimeter. Use this tool first to discover a topic and
        obtain its slug, then pass that slug to `list_topic_elements` to
        browse its datasets, or to `get_topic_catalog` to retrieve its
        contextualization catalog when one is declared.

        Leave `query` empty to browse topics.

        Typical workflow: search_topics → list_topic_elements → get_topic_catalog.
        """
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        try:
            result = await datagouv_api_client.search_topics(
                query=query,
                page=page,
                page_size=page_size,
            )
        except niquests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None:
                return f"Error: HTTP {status} - {str(e)}"
            return f"Error: {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"

        topics = result.get("data", [])
        label = f"for query: '{query}'" if query else "(browsing all topics)"
        if not topics:
            return f"No topics found {label}"

        site_base = env_config.get_base_url("site").rstrip("/")
        content_parts = [
            f"Found {result.get('total', len(topics))} topic(s) {label}",
            f"Page {result.get('page', page)} of results:\n",
        ]
        for i, topic in enumerate(topics, 1):
            slug = topic.get("slug") or topic.get("id")
            content_parts.append(f"{i}. {topic.get('name', 'Untitled')}")
            content_parts.append(f"   Slug: {slug}")
            if topic.get("id"):
                content_parts.append(f"   ID: {topic.get('id')}")
            if topic.get("description"):
                desc = str(topic.get("description", ""))[:200]
                content_parts.append(f"   Description: {desc}...")
            org = topic.get("organization")
            if isinstance(org, dict) and org.get("name"):
                content_parts.append(f"   Organization: {org.get('name')}")
            tags = topic.get("tags") or []
            if tags:
                content_parts.append(f"   Tags: {', '.join(tags[:5])}")
            mcp_extras = (topic.get("extras") or {}).get("mcp") or {}
            if mcp_extras.get("catalog_dataset_id"):
                content_parts.append(
                    "   Contextualization catalog: yes (use get_topic_catalog)"
                )
            content_parts.append(
                f"   URL: {topic.get('page') or f'{site_base}/topics/{slug}/'}"
            )
            content_parts.append("")

        return "\n".join(content_parts)
