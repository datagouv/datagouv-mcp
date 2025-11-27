from mcp.server.fastmcp import FastMCP

from tools.download_and_parse_resource import (
    register_download_and_parse_resource_tool,
)
from tools.get_dataset_info import register_get_dataset_info_tool
from tools.get_metrics import register_get_metrics_tool
from tools.get_resource_info import register_get_resource_info_tool
from tools.list_dataset_resources import register_list_dataset_resources_tool
from tools.query_dataset_data import register_query_dataset_data_tool
from tools.search_datasets import register_search_datasets_tool


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools with the provided FastMCP instance."""
    register_search_datasets_tool(mcp)
    register_query_dataset_data_tool(mcp)
    register_get_dataset_info_tool(mcp)
    register_list_dataset_resources_tool(mcp)
    register_get_resource_info_tool(mcp)
    register_download_and_parse_resource_tool(mcp)
    register_get_metrics_tool(mcp)
