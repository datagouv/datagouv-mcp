"""Unit tests for shared helpers backing plain + interactive MCP tools."""

from fastmcp.tools import ToolResult

from tools.get_metrics import _metrics_panels_to_text, _MetricsPanel
from tools.list_dataset_resources import _format_filesize
from tools.query_resource_data import _tabular_rows_for_table
from tools.search_dataservices import (
    _search_dataservices_rows,
    _search_dataservices_text,
)
from tools.search_datasets import _search_datasets_rows, _search_datasets_text
from tools.search_organizations import (
    _search_organizations_rows,
    _search_organizations_text,
)


def test_search_datasets_helpers() -> None:
    result = {
        "total": 1,
        "page": 1,
        "data": [
            {
                "title": "My Dataset",
                "id": "abc",
                "organization": "Org",
                "tags": ["a", "b"],
                "resources_count": 3,
                "url": "https://example.com",
                "description_short": "Short desc",
            }
        ],
    }
    text = _search_datasets_text("water", result)
    assert "My Dataset" in text
    assert "water" in text
    rows = _search_datasets_rows(result["data"])
    assert rows[0]["id"] == "abc"
    assert rows[0]["resources_count"] == 3


def test_search_organizations_helpers() -> None:
    result = {
        "total": 1,
        "page": 1,
        "data": [
            {
                "name": "Org Name",
                "acronym": "ON",
                "id": "o1",
                "slug": "org-name",
                "badges": ["certified"],
                "metrics": {"datasets": 5},
                "url": "https://u",
                "profile_url": "https://p",
            }
        ],
    }
    text = _search_organizations_text(
        "x", result, badge=None, name=None, business_number_id=None, sort=None
    )
    assert "Org Name" in text
    assert "ON" in text
    rows = _search_organizations_rows(result["data"])
    assert rows[0]["slug"] == "org-name"


def test_search_dataservices_helpers() -> None:
    result = {
        "total": 1,
        "page": 1,
        "data": [
            {
                "title": "API X",
                "id": "d1",
                "organization": "ACME",
                "base_api_url": "https://api.example",
                "tags": ["t1"],
                "url": "https://catalog",
                "description": "Desc",
            }
        ],
    }
    text = _search_dataservices_text("geo", result)
    assert "API X" in text
    rows = _search_dataservices_rows(result["data"])
    assert rows[0]["base_api_url"] == "https://api.example"


def test_metrics_panels_to_text_dataset() -> None:
    panels = [
        _MetricsPanel(
            kind="dataset",
            metadata_lines=["Dataset Metrics: T", "Dataset ID: x", ""],
            rows=[{"month": "2024-01", "visits": 10, "downloads": 5}],
        )
    ]
    text = _metrics_panels_to_text(panels)
    assert "2024-01" in text
    assert "10" in text


def test_metrics_panels_to_text_resource() -> None:
    panels = [
        _MetricsPanel(
            kind="resource",
            metadata_lines=["Resource Metrics: R", "Resource ID: y", ""],
            rows=[{"month": "2024-02", "downloads": 3}],
        )
    ]
    text = _metrics_panels_to_text(panels)
    assert "2024-02" in text
    assert "3" in text


def test_tabular_rows_for_table() -> None:
    rows = _tabular_rows_for_table([{"a": 1, "b": None, "c": "x" * 600}])
    assert rows[0]["a"] == "1"
    assert rows[0]["b"] == ""
    assert len(rows[0]["c"]) <= 503


def test_format_filesize() -> None:
    assert "KB" in _format_filesize(2048)
    assert _format_filesize(None) == ""


def test_tool_result_text_only() -> None:
    tr = ToolResult(content="summary", structured_content=None)
    assert tr.structured_content is None
    assert any(block.type == "text" for block in tr.content)
