from mcp.server.fastmcp import FastMCP

from mcp_resources.catalog_overview import register_catalog_overview_resource


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources with the provided FastMCP instance."""
    register_catalog_overview_resource(mcp)
