"""Unit tests for the topic MCP tools (mocked API client)."""

from unittest.mock import AsyncMock, MagicMock, patch

import niquests
import pytest
from mcp.server.fastmcp import FastMCP

from tools import register_tools


@pytest.fixture
def mcp() -> FastMCP:
    app = FastMCP()
    register_tools(app)
    return app


def _http_error(status: int) -> niquests.HTTPError:
    response = MagicMock()
    response.status_code = status
    error = niquests.HTTPError(f"HTTP {status}")
    error.response = response
    return error


async def _call(mcp: FastMCP, name: str, **kwargs) -> str:
    result = await mcp.call_tool(name, kwargs)
    # FastMCP returns a list of content blocks (or a tuple with structured content)
    blocks = result[0] if isinstance(result, tuple) else result
    return "\n".join(getattr(b, "text", "") for b in blocks)


TOPIC_WITH_CATALOG = {
    "id": "topic123",
    "name": "Univers Culture DEPS",
    "slug": "univers-culture-deps",
    "extras": {"mcp": {"catalog_dataset_id": "cat456", "version": "1.0"}},
}

TOPIC_WITHOUT_CATALOG = {
    "id": "topic789",
    "name": "Plain topic",
    "slug": "plain-topic",
    "extras": {},
}

CATALOG_DATASET = {
    "id": "cat456",
    "title": "Catalogue topic univers-culture-deps",
    "resources": [
        {
            "id": "res1",
            "title": "catalog_datasets",
            "format": "csv",
            "url": "http://x/1",
        },
        {"id": "res2", "title": "catalog_schema", "format": "csv", "url": "http://x/2"},
    ],
}


@pytest.mark.asyncio
class TestGetTopicCatalog:
    async def test_with_catalog(self, mcp):
        with (
            patch(
                "helpers.datagouv_api_client.get_topic_details",
                new=AsyncMock(return_value=TOPIC_WITH_CATALOG),
            ),
            patch(
                "helpers.datagouv_api_client.get_dataset_details",
                new=AsyncMock(return_value=CATALOG_DATASET),
            ),
        ):
            text = await _call(
                mcp, "get_topic_catalog", topic_id="univers-culture-deps"
            )

        assert "Slug: univers-culture-deps" in text
        assert "Catalog dataset ID: cat456" in text
        assert "Convention version: 1.0" in text
        assert "catalog_datasets" in text
        assert "Resource ID: res2" in text

    async def test_without_catalog(self, mcp):
        with patch(
            "helpers.datagouv_api_client.get_topic_details",
            new=AsyncMock(return_value=TOPIC_WITHOUT_CATALOG),
        ):
            text = await _call(mcp, "get_topic_catalog", topic_id="plain-topic")

        assert "No contextualization catalog" in text
        assert "list_topic_elements" in text
        assert "Catalog dataset ID" not in text

    async def test_topic_not_found(self, mcp):
        with patch(
            "helpers.datagouv_api_client.get_topic_details",
            new=AsyncMock(side_effect=_http_error(404)),
        ):
            text = await _call(mcp, "get_topic_catalog", topic_id="nope")

        assert "Topic 'nope' not found" in text

    async def test_catalog_unreachable(self, mcp):
        with (
            patch(
                "helpers.datagouv_api_client.get_topic_details",
                new=AsyncMock(return_value=TOPIC_WITH_CATALOG),
            ),
            patch(
                "helpers.datagouv_api_client.get_dataset_details",
                new=AsyncMock(side_effect=_http_error(404)),
            ),
        ):
            text = await _call(
                mcp, "get_topic_catalog", topic_id="univers-culture-deps"
            )

        assert "could not be retrieved" in text
        assert "cat456" in text
