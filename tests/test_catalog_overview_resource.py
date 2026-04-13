import pytest

from main import mcp
from mcp_resources.catalog_overview import CATALOG_OVERVIEW_URI


@pytest.mark.asyncio
async def test_catalog_overview_resource_is_listed():
    resources = await mcp.list_resources()

    resource = next(
        (item for item in resources if str(item.uri) == CATALOG_OVERVIEW_URI), None
    )

    assert resource is not None
    assert resource.name == "catalog_overview"
    assert resource.title == "Catalog Scope and Discovery Guide"
    assert resource.mimeType == "text/markdown"
    assert resource.description is not None


@pytest.mark.asyncio
async def test_catalog_overview_resource_content_uses_current_environment(monkeypatch):
    monkeypatch.setenv("DATAGOUV_API_ENV", "demo")

    contents = list(await mcp.read_resource(CATALOG_OVERVIEW_URI))

    assert len(contents) == 1
    content = contents[0].content
    assert isinstance(content, str)
    assert (
        "This MCP server does not ship a fixed, preloaded list of datasets." in content
    )
    assert "Current catalog site: https://demo.data.gouv.fr/" in content
    assert "search_datasets" in content
    assert "search_dataservices" in content
    assert "query_resource_data" in content
