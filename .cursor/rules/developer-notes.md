# Developer Notes

This file contains implementation details that future contributors (human or LLM) should keep in mind when evolving the MCP server.

## Repository layout

```
├─ main.py                # FastMCP entry point, tool/resource definitions
└─ helpers/
   ├─ datagouv_api_client.py   # HTTP client helper functions (data.gouv API)
   └─ hydra_db.py              # Async psycopg helper for the Hydra/Postgres CSV DB
```

`.cursor/rules/` (this folder) should stay with the code when migrating to a dedicated repo.

## Configuration

- `DATAGOUV_ENV` selects the target platform (`prod` by default; set to `demo` only when testing against the staging APIs). The helpers derive both API and public-site URLs from this variable.
- `MCP_PORT` defaults to 8000 if not set. Example: `MCP_PORT=8007 uv run main.py` to use a custom port.
- `HYDRA_DB_HOST/PORT/USER/PASSWORD/NAME` control how `helpers/hydra_db.py` connects to the Hydra CSV Postgres database (defaults match the local Docker compose stack at `127.0.0.1:5434`, user/password `postgres`).
- A `.env.example` template exists so you can `cp .env.example .env` and tweak values locally (including Hydra/PostgREST settings if needed).
- The `CHANGELOG.md` file is generated automatically by `tag_version.sh` when creating a release tag—do not edit it manually between releases.

## datagouv_api_client helpers

| Function | Endpoint | Notes |
| --- | --- | --- |
| `search_datasets` | `GET /1/datasets/` | Handles tags returned as strings or `{name: ...}` objects. |
| `get_dataset_metadata` | `GET /1/datasets/{id}/` | Returns title + descriptions. |
| `get_resource_metadata` | `GET /2/datasets/resources/{id}/` | Uses API v2 because it exposes richer resource info. |
| `get_resources_for_dataset` | `GET /1/datasets/{id}/` | Returns dataset metadata plus `(id, title)` tuple list for resources. |
| `get_resource_and_dataset_metadata` | Combines v1 + v2 | Fetches resource first, then dataset if available. |
| `create_dataset` | `POST /1/datasets/` | Requires `X-Api-Key`. Raises a `ClientResponseError` with 401 details if the key is invalid. |

Implementation tips:
- The helper functions accept an optional `aiohttp.ClientSession`. They create/close their own session when `session is None`, avoiding "Unclosed client session" warnings.
- On POST requests, always set `"Content-Type": "application/json"` and `"Accept": "application/json"`.
- Keep timeouts conservative (current default: 15s for GET, 30s for POST).

## Adding tools/resources

1. **Define your helper** in `datagouv_api_client.py` (with tests if possible).
2. **Create the MCP tool/resource** in `server.py`.
   - Tools should return strings. Format them for readability (headings, bullet points).
   - Resources should provide enough context for an LLM to make subsequent tool calls.
3. **Update docs** (this folder) with any new expectations or workflows.

## Error handling patterns

- Tool failures should return a human-readable string, not an exception. This keeps MCP Inspector / clients friendly.
- Include HTTP status and server messages (`UNAUTHORIZED: {...}`) when available.
- Mention demo-versus-production key differences explicitly to reduce confusion.

## Logging / Debugging

- Temporary `print()` statements are acceptable during development but should be removed or guarded behind a flag before release.
- The server already logs every MCP request type (thanks to FastMCP). Additional logging should be lightweight and contextual.

## Known constraints

- Streamable HTTP is the only supported transport today. If you need STDIO, you must wrap `FastMCP` differently.
- Session stickiness: removing `stateless_http=True` eliminated `ClosedResourceError` when clients connect/disconnect rapidly. Keep the default behavior unless FastMCP introduces a fix.
- API keys: the server does not store them; each request must provide it explicitly. This avoids mixing credentials when multiple clients connect.
