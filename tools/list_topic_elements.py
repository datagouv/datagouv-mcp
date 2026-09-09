import asyncio
from typing import Any

import niquests
from mcp.server.fastmcp import FastMCP

from helpers import datagouv_api_client, env_config
from helpers.logging import log_tool
from helpers.mcp_tool_defaults import READ_ONLY_EXTERNAL_API_TOOL


async def _fetch_dataset_titles(dataset_ids: list[str]) -> dict[str, dict[str, Any]]:
    """
    Fetch dataset metadata concurrently (bounded) for the given IDs.

    Topic elements only carry a reference (class + id), so titles must be
    resolved separately. Failures are ignored: the element is then listed
    with its ID only.
    """
    semaphore = asyncio.Semaphore(5)

    async def fetch(dataset_id: str) -> tuple[str, dict[str, Any] | None]:
        async with semaphore:
            try:
                return dataset_id, await datagouv_api_client.get_dataset_details(
                    dataset_id
                )
            except Exception:  # noqa: BLE001
                return dataset_id, None

    results = await asyncio.gather(*(fetch(d) for d in dataset_ids))
    return {dataset_id: data for dataset_id, data in results if data}


def register_list_topic_elements_tool(mcp: FastMCP) -> None:
    @mcp.tool(
        title="List topic elements",
        annotations=READ_ONLY_EXTERNAL_API_TOOL,
    )
    @log_tool
    async def list_topic_elements(
        topic_id: str,
        page: int = 1,
        page_size: int = 20,
        element_class: str | None = "Dataset",
    ) -> str:
        """
        List the elements (datasets by default) attached to a data.gouv.fr topic.

        Use this tool to explore the perimeter of a topic identified by its
        slug or ID (obtained from `search_topics`). Each dataset element
        comes with its dataset ID, which can be passed to `get_dataset_info`
        or `list_dataset_resources`.

        Set `element_class` to another class (e.g. "Reuse") to list other
        kinds of elements, or to None to list all classes.

        Typical workflow: search_topics → list_topic_elements → list_dataset_resources.
        """
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)

        try:
            result = await datagouv_api_client.get_topic_elements(
                topic_id=topic_id,
                page=page,
                page_size=page_size,
                element_class=element_class,
            )
        except niquests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status == 404:
                return f"Error: Topic '{topic_id}' not found."
            if status is not None:
                return f"Error: HTTP {status} - {str(e)}"
            return f"Error: {str(e)}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {str(e)}"

        elements = result.get("data", [])
        class_label = element_class or "all classes"
        if not elements:
            return f"No elements ({class_label}) found for topic '{topic_id}'."

        site_base = env_config.get_base_url("site").rstrip("/")

        # Elements only reference their object; resolve dataset titles.
        dataset_ids = [
            e["element"]["id"]
            for e in elements
            if isinstance(e.get("element"), dict)
            and e["element"].get("class") == "Dataset"
            and e["element"].get("id")
        ]
        datasets = await _fetch_dataset_titles(dataset_ids) if dataset_ids else {}

        content_parts = [
            f"Found {result.get('total', len(elements))} element(s) "
            f"({class_label}) for topic '{topic_id}'",
            f"Page {result.get('page', page)} of results:\n",
        ]
        for i, item in enumerate(elements, 1):
            element = (
                item.get("element") if isinstance(item.get("element"), dict) else {}
            )
            klass = element.get("class") or class_label
            object_id = element.get("id")
            dataset = datasets.get(object_id, {}) if klass == "Dataset" else {}

            title = item.get("title") or dataset.get("title") or f"{klass} {object_id}"
            content_parts.append(f"{i}. {title}")
            content_parts.append(f"   Class: {klass}")
            if object_id:
                content_parts.append(f"   {klass} ID: {object_id}")
            description = item.get("description") or dataset.get("description_short")
            if description:
                content_parts.append(f"   Description: {str(description)[:200]}...")
            org = dataset.get("organization")
            if isinstance(org, dict) and org.get("name"):
                content_parts.append(f"   Organization: {org.get('name')}")
            tags = item.get("tags") or dataset.get("tags") or []
            if tags:
                content_parts.append(f"   Tags: {', '.join(tags[:5])}")
            if klass == "Dataset" and object_id:
                content_parts.append(f"   URL: {site_base}/datasets/{object_id}/")
            content_parts.append("")

        return "\n".join(content_parts)
