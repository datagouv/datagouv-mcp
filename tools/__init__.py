from fastmcp import FastMCP

from tools.get_dataservice_info import register_get_dataservice_info_tool
from tools.get_dataservice_openapi_spec import (
    register_get_dataservice_openapi_spec_tool,
)
from tools.get_dataset_info import register_get_dataset_info_tool
from tools.get_metrics import (
    register_get_metrics_tool,
    register_get_metrics_visual_tool,
)
from tools.get_resource_info import register_get_resource_info_tool
from tools.list_dataset_resources import (
    register_list_dataset_resources_tool,
    register_list_dataset_resources_visual_tool,
)
from tools.query_resource_data import (
    register_query_resource_data_tool,
    register_query_resource_data_visual_tool,
)
from tools.search_dataservices import (
    register_search_dataservices_tool,
    register_search_dataservices_visual_tool,
)
from tools.search_datasets import (
    register_search_datasets_tool,
    register_search_datasets_visual_tool,
)
from tools.search_organizations import (
    register_search_organizations_tool,
    register_search_organizations_visual_tool,
)


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools with the provided FastMCP instance."""
    register_search_datasets_tool(mcp)
    register_search_datasets_visual_tool(mcp)
    register_search_organizations_tool(mcp)
    register_search_organizations_visual_tool(mcp)
    register_search_dataservices_tool(mcp)
    register_search_dataservices_visual_tool(mcp)
    register_get_dataservice_info_tool(mcp)
    register_get_dataservice_openapi_spec_tool(mcp)
    register_query_resource_data_tool(mcp)
    register_query_resource_data_visual_tool(mcp)
    register_get_dataset_info_tool(mcp)
    register_list_dataset_resources_tool(mcp)
    register_list_dataset_resources_visual_tool(mcp)
    register_get_resource_info_tool(mcp)
    register_get_metrics_tool(mcp)
    register_get_metrics_visual_tool(mcp)
