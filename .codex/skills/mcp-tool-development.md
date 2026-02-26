---
name: mcp-tool-development
description: Implement, refactor, or debug MCP tool modules in this repository. Use when requests mention adding/modifying/removing tools, changing tool output text, registering tools, or wiring new data.gouv.fr capabilities through FastMCP.
prerequisites: uv, python>=3.13, repository dependencies installed via `uv sync`
---

# MCP Tool Development

<purpose>
Build or modify `tools/*.py` safely while preserving the project contract: tools are read-only, async, and return user-readable strings.
</purpose>

<context>
- Tool modules live in `tools/` and expose `register_<name>_tool(mcp: FastMCP)`.
- Registration happens centrally in `tools/__init__.py` via `register_tools(mcp)`.
- Tool functions are decorated with `@mcp.tool()` and return `str`.
- Business/API calls belong in `helpers/`, not inside tool formatting loops.
- `main.py` calls `register_tools(mcp)` once during startup.
</context>

<procedure>
1. Identify target behavior and owning tool file in `tools/`.
2. Decision point: if API/data retrieval logic is missing, implement/update helper in `helpers/` first; otherwise continue.
3. Implement tool behavior with strict input validation and bounded parameters.
4. Format output as concise readable text; avoid raw JSON dumps.
5. Register new tool in `tools/__init__.py` if creating a new module.
6. Add/adjust tests in `tests/`.
7. Run validation:
- `uv run pytest -q`
- `uv run ruff check --select I .`
- `uv run ruff format --check .`
- `uv run ty check`
8. If touching gated files (`main.py`, env config, dependencies), stop and request approval.
</procedure>

<patterns>
<do>
- Return readable sections (`title`, IDs, key fields, warnings).
- Catch `httpx.HTTPStatusError` and convert to user-friendly messages.
- Clamp page/page_size and filter inputs before calling APIs.
- Use project logger name: `logging.getLogger("datagouv_mcp")`.
</do>
<dont>
- Don’t return large raw payloads when summarized output is enough -> summarize with key fields.
- Don’t call external APIs directly from many tools -> centralize in `helpers/*`.
- Don’t add write operations (create/update/delete) -> keep tools read-only.
- Don’t forget `tools/__init__.py` registration -> tool stays unreachable.
</dont>
</patterns>

<examples>
Example: New tool registration pattern
```python
# tools/example_tool.py
from mcp.server.fastmcp import FastMCP


def register_example_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    async def example_tool(resource_id: str) -> str:
        return f"Resource ID: {resource_id}"
```

Example: Wire into registry
```python
# tools/__init__.py
from tools.example_tool import register_example_tool


def register_tools(mcp: FastMCP) -> None:
    register_example_tool(mcp)
```
</examples>

<troubleshooting>
| Symptom | Cause | Fix |
|---|---|---|
| Tool not visible in MCP client | Not imported/registered in `tools/__init__.py` | Add import + `register_*` call |
| `ResourceNotAvailableError` text in output | Resource unsupported by Tabular API | Route user to `download_and_parse_resource` |
| Tool crashes with traceback | Uncaught exception in tool | Catch exceptions and return readable error string |
| Duplicate API calls causing slowness | Helper called repeatedly without session reuse | Reuse one `httpx.AsyncClient` in loop |
</troubleshooting>

<references>
- `tools/__init__.py`: central tool registration order.
- `tools/query_resource_data.py`: complex tool with filters/sort and graceful fallbacks.
- `tools/get_resource_info.py`: metadata + availability checks pattern.
- `main.py`: server initialization and `register_tools(mcp)` call site.
</references>
