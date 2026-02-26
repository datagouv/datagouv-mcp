---
name: api-client-integration
description: Extend or debug helper API clients under `helpers/` when work involves HTTP calls, environment-specific base URLs, session ownership, timeouts, or response parsing for data.gouv.fr, Tabular, Metrics, or Crawler APIs.
prerequisites: uv, network access, understanding of async httpx
---

# API Client Integration

<purpose>
Implement reliable helper-layer HTTP integrations that tools can consume without duplicating networking logic.
</purpose>

<context>
- Helper files: `helpers/datagouv_api_client.py`, `helpers/tabular_api_client.py`, `helpers/metrics_api_client.py`, `helpers/crawler_api_client.py`.
- `helpers/env_config.py` is the single source of environment base URLs.
- Session ownership pattern is required: helper creates/closes client only when no session is passed.
- Helpers return structured Python data (`dict`, `list`) and may raise HTTP/parsing errors.
</context>

<procedure>
1. Select the owning helper module by API domain.
2. Confirm required base URL key exists in `helpers/env_config.py`.
3. Add async helper function with explicit timeout and typed return shape.
4. Reuse optional `httpx.AsyncClient` parameter (`session`) when chaining calls.
5. Validate HTTP behavior:
- `raise_for_status()` for non-success responses
- custom exception only when behavior needs tool-level branching
6. Add/adjust tests in `tests/` for happy path + invalid IDs.
7. Run `uv run pytest -q` and quality commands.
8. If URL policy/env switching must change, request approval before editing `helpers/env_config.py`.
</procedure>

<patterns>
<do>
- Keep URL building close to helper logic and use `env_config.get_base_url(...)`.
- Log request intent and bounded context (URL/ID), not secrets.
- Cap externally-controlled limits (`min/max`) before requests.
- Isolate parsing logic (`fetch_openapi_spec`, CSV/JSON parsing helpers).
</do>
<dont>
- Don’t hardcode `https://www.data.gouv.fr/...` in helper bodies -> derive from env config.
- Don’t return raw `httpx.Response` objects -> return parsed data.
- Don’t leak client lifecycle -> always close owned clients in `finally`.
- Don’t place MCP output formatting in helpers -> keep formatting in `tools/`.
</dont>
</patterns>

<examples>
Example: Optional session ownership pattern
```python
async def _get_session(session: httpx.AsyncClient | None) -> tuple[httpx.AsyncClient, bool]:
    if session is not None:
        return session, False
    return httpx.AsyncClient(), True
```

Example: Base URL usage
```python
base_url = env_config.get_base_url("datagouv_api")
url = f"{base_url}1/datasets/{dataset_id}/"
```
</examples>

<troubleshooting>
| Symptom | Cause | Fix |
|---|---|---|
| Wrong environment data returned | `DATAGOUV_ENV` unset/invalid | Set `DATAGOUV_ENV=demo|prod`; invalid defaults to `prod` |
| 404 on known endpoint | Wrong API version path (`v1` vs `v2`) | Match existing endpoint patterns in helper module |
| `Unclosed client session` warnings | Missing close in owned session path | Ensure `finally: await session.aclose()` |
| Metrics call fails in demo | Metrics API is prod-only | Guard in tool layer; use prod env |
</troubleshooting>

<references>
- `helpers/env_config.py`: environment target matrix.
- `helpers/datagouv_api_client.py`: v1/v2 endpoint and OpenAPI parsing patterns.
- `helpers/tabular_api_client.py`: custom exception + metadata links handling.
- `helpers/crawler_api_client.py`: in-memory TTL cache pattern.
</references>
