# data.gouv.fr MCP Server — Overview

This document captures the key concepts behind the `api_tabular/mcp` implementation so the work can be moved into a dedicated repository without losing any context.

## Goals

- Provide a Model Context Protocol (MCP) server that exposes data.gouv.fr datasets and resources to LLM clients such as Cursor, Windsurf, Claude Desktop, Gemini CLI, etc.
- Offer a small set of tools that a chatbot can call to (a) discover datasets and (b) create datasets programmatically.
- Expose MCP dynamic resources so the client can fetch dataset/resource metadata via `resources/read`.
- Rely either on the **demo** environment or the **prod** environment: the base URL automatically switches between `https://demo.data.gouv.fr/api/` and `https://www.data.gouv.fr/api/` using the `DATAGOUV_ENV` environment variable (defaults to **prod**). A `.env.example` template is included so you can copy/edit env vars quickly.

## Architecture

### FastMCP server

- The server lives in `main.py` and instantiates a single `FastMCP` app.
- Transport: **Streamable HTTP** only. The server is launched with `uvicorn mcp.streamable_http_app()` and listens on `0.0.0.0`.
- There is **no** STDIO or SSE mode. `stateless_http=True` was removed because it caused `anyio.ClosedResourceError`; default FastMCP session handling works fine.
- `MCP_PORT` environment variable is mandatory. No default port is baked in for now.

### Tools

| Tool | Purpose | Data source |
| --- | --- | --- |
| `search_datasets` | Keyword search across datasets (title/description/tags). Returns a formatted text summary with metadata and resource counts. | data.gouv.fr API v1 – `GET /1/datasets/` |
| `create_dataset` | Creates a dataset (public or draft). Requires an API key supplied by the MCP client. Returns textual confirmation with dataset id/slug. | data.gouv.fr API v1 – `POST /1/datasets/` |

Implementation details:
- Both tools are annotated with `@mcp.tool()` and return plain strings (LLMs handle free-form text better in this case).
- `create_dataset` expects the API key to be provided via the MCP client configuration (`config.apiKey`). The tool parameter wins; if absent, the request is rejected with an explanatory message. We intentionally removed server-side environment fallbacks to avoid ambiguity.
- HTTP errors (401/400/403/others) are caught and rendered as readable text for the LLM.

### Resources

Three `@mcp.resource` definitions exist:

1. `datagouv://resources` — static list describing the available resource templates and the expected workflow.
2. `datagouv://dataset/{dataset_id}` — fetches dataset metadata plus all resources, so the LLM can discover resource IDs before querying data.
3. `datagouv://resource/{resource_id}` — fetches resource metadata plus the associated dataset information.

Both dynamic resources rely on helper functions in `datagouv_api_client.py` that orchestrate the v1 and v2 endpoints.

### HTTP client layer

- `helpers/datagouv_api_client.py` wraps all calls to data.gouv.fr API (demo or prod).
- Dataset search + metadata rely on API **v1**; resource metadata relies on API **v2**.
- Sessions are created ad hoc if not provided, and always closed in `finally` blocks to avoid unclosed connector warnings.
- `DATAGOUV_ENV` picks between the demo/prod hosts.

## Running locally

```bash
# Install project deps (uv preferred)
uv sync

# Start Hydra/PostgREST stack if you need the main API
docker compose --profile hydra up -d

# Copy + edit environment file
cp .env.example .env

# Load env + start MCP server (MCP_PORT is required)
set -a && source .env && set +a
uv run main.py
```

The server logs each tool call (`Processing request of type ...`). When `create_dataset` runs with `DEBUG` print statements enabled you will see the key prefix/suffix to confirm the MCP client passed the intended key.

## MCP client expectations

- Clients must send requests via the Streamable HTTP transport (`POST/GET /mcp`).
- `resources/list` will show the static resource; dynamic resources are discoverable through `resources/templates/list`.
- To call `create_dataset`, clients must supply `api_key` in the tool arguments. In Cursor this is achieved by adding `"config": {"apiKey": "..."}` under the MCP server definition.
- Keys must belong to the environment selected via `DATAGOUV_ENV`. Demo mode rejects production keys and vice-versa.

## Adding new capabilities

1. **New Tool**: create an async function, decorate with `@mcp.tool()`, leverage helpers in `datagouv_api_client`. Keep output textual unless structured data is absolutely needed by the downstream workflow.
2. **New Resource**: use `@mcp.resource(uri_template, ...)`. Fetch metadata via `datagouv_api_client`. Return concise descriptive text so the LLM can ingest it easily.
3. **HTTP helper**: extend `datagouv_api_client` with additional v1/v2/vX endpoints. Always close sessions, and raise informative errors (e.g., include response body for 4xx).

## Deployment checklist

- Ensure `DATAGOUV_ENV` is set correctly for the environment you deploy to so dataset links keep pointing to the right public site.
- Expose `MCP_PORT` and optionally `MCP_HOST` via the surrounding process manager; the FastMCP app itself is stateless.
- Front the service with HTTPS if exposed publicly. Clients such as Cursor expect HTTPS in production.
- If moving to a dedicated repository, keep `/mcp/docs` with this document and any client-specific instructions so future contributors (human or LLM) understand the constraints.
