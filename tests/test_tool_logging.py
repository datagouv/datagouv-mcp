import ast
import logging

import pytest
from fastmcp import FastMCP
from pytest_httpx import HTTPXMock

from helpers.logging import TOOLS_LOGGER_NAME
from tools import register_tools


@pytest.fixture
def mcp():
    app = FastMCP()
    register_tools(app)
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name, call_args, expected_kwargs",
    [
        (
            "search_datasets",
            {"query": "population"},
            {"query": "population", "page": 1, "page_size": 20},
        ),
        (
            "search_datasets",
            {"query": "education", "page": 2},
            {"query": "education", "page": 2, "page_size": 20},
        ),
        (
            "search_dataservices",
            {"query": "api"},
            {"query": "api", "page": 1, "page_size": 20},
        ),
        ("get_dataset_info", {"dataset_id": "abc123"}, {"dataset_id": "abc123"}),
    ],
)
async def test_tool_logs_kwargs(
    mcp: FastMCP,
    caplog,
    httpx_mock: HTTPXMock,
    monkeypatch,
    tool_name: str,
    call_args: dict,
    expected_kwargs: dict,
):
    monkeypatch.setattr("helpers.matomo.MATOMO_URL", "https://matomo.example.com")
    monkeypatch.setattr("helpers.matomo.MATOMO_SITE_ID", "1")
    httpx_mock.add_response(json={})  # Mock tool call
    httpx_mock.add_response(json={})  # Mock Matomo call
    with caplog.at_level(logging.INFO, logger=TOOLS_LOGGER_NAME):
        await mcp.call_tool(tool_name, call_args)

    record = next(r for r in caplog.records if tool_name in r.message)

    kwargs_str = record.message.split("kwargs=")[1]
    kwargs = ast.literal_eval(kwargs_str)

    for key, value in expected_kwargs.items():
        assert kwargs[key] == value, f"Expected {key}={value}, got {kwargs.get(key)}"
