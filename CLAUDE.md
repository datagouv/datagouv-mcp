<identity>
data.gouv.fr MCP server exposes read-only dataset, resource, dataservice, and metrics access from data.gouv.fr APIs through Streamable HTTP MCP tools.
</identity>

<stack>
| Layer | Technology | Version | Notes |
|---|---|---|---|
| Runtime | Python | `>=3.13,<3.15` | Pinned in `pyproject.toml` and `uv.lock` |
| Language | Python | 3.13+ | Async-first with `httpx` |
| MCP framework | `mcp` (Python SDK) | `1.26.0` | Constraint: `>=1.25.0,<2` |
| ASGI server | `uvicorn` | `0.40.0` | Started in `main.py` |
| HTTP client | `httpx` | `0.28.1` | Used by all API helpers |
| Package manager | `uv` | `0.9.18` [verify] | Use `uv sync` and `uv run` only |
| Testing | `pytest` + `pytest-asyncio` | `9.0.2` + `1.3.0` | 57 tests (`uv run pytest -q`) |
| Lint/format | `ruff` | `0.14.14` | Import sorting + formatting |
| Type check | `ty` | `0.0.18` | `uv run ty check` |
| CI | CircleCI | config v2.1 | Lint + type + tests on `main` |
| Container | `astral/uv:python3.14-trixie-slim` | [verify] | `Dockerfile` base image |
</stack>

<structure>
Module boundaries are strict:
- `tools/` = MCP presentation layer (`@mcp.tool()` functions, always returns `str`).
- `helpers/` = API integration layer (async HTTP calls, structured Python data).
- `main.py` = server composition, transport security, `/health`, process startup.
- `tests/` = integration-heavy validation for helpers and server health.

Top-level layout:
- `main.py` - FastMCP app, transport security, `/health`, uvicorn entrypoint. [agent: modify with approval]
- `helpers/`
- `helpers/datagouv_api_client.py` - Dataset/resource/dataservice API wrappers. [agent: create/modify]
- `helpers/tabular_api_client.py` - Tabular API wrappers and `ResourceNotAvailableError`. [agent: create/modify]
- `helpers/metrics_api_client.py` - Metrics API wrappers. [agent: create/modify]
- `helpers/crawler_api_client.py` - Exceptions-list caching for large resources. [agent: create/modify]
- `helpers/env_config.py` - Base URL environment switch (`DATAGOUV_ENV`). [agent: modify with approval]
- `tools/` - One file per MCP tool + registration in `tools/__init__.py`. [agent: create/modify]
- `tests/` - Pytest suite (networked integration tests + local health test). [agent: create/modify]
- `.circleci/config.yml` - CI jobs and branch filters. [agent: modify with approval]
- `Dockerfile`, `docker-compose.yml` - Local/prod container runtime config. [agent: modify with approval]
- `pyproject.toml`, `uv.lock` - Dependency contract. [agent: modify with approval]
- `tag_version.sh` - Release/tag/changelog automation. [agent: modify with approval]
- `.cursor/rules/` - Auxiliary docs; some entries are stale vs current codebase. [agent: read/limited edits]
- `CLAUDE.md`, `agents.md`, `.codex/skills/` - Agentic context layer. [agent: create/modify only when asked]
</structure>

<commands>
| Task | Command | Notes |
|---|---|---|
| Install deps | `uv sync --frozen` | CI-compatible install |
| Install deps (dev local) | `uv sync` | Uses `uv.lock` |
| Run server | `uv run python main.py` | Binds `MCP_HOST`/`MCP_PORT` |
| Health check | `curl http://127.0.0.1:${MCP_PORT:-8000}/health` | Returns status/timestamp/version |
| Test all | `uv run pytest -q` | Verified: 57 passed in ~11s |
| Test single file | `uv run pytest tests/test_health_endpoint.py -q` | Fast local smoke test |
| Lint imports | `uv run ruff check --select I .` | CI lint rule |
| Format check | `uv run ruff format --check .` | CI format rule |
| Autofix lint+format | `uv run ruff check --fix . && uv run ruff format .` | Pre-PR cleanup |
| Type check | `uv run ty check` | Must pass before PR |
| Release dry run | `./tag_version.sh <version> --dry-run` | Requires `gh`; approval required |
| Release | `./tag_version.sh <version>` | Pushes commit/tag + creates GH release |
</commands>

<conventions>
  <code_style>
  - Naming: `snake_case` for functions/variables/files, `UPPER_SNAKE_CASE` for constants, `PascalCase` only for classes/exceptions.
  - Imports: stdlib -> third-party -> local packages (`helpers`, `tools`); keep absolute imports.
  - Async boundaries: all network helpers are `async` and accept optional `httpx.AsyncClient`.
  - Tool return type: MCP tools return user-readable `str`, not dict/json payloads.
  - Logging: use `logging.getLogger("datagouv_mcp")` consistently.
  - Error handling: helpers raise HTTP/parse errors; tools catch and convert to readable error strings.
  </code_style>

  <patterns>
    <do>
    - Add/extend helper functions in `helpers/` before adding tool logic.
    - Reuse one `httpx.AsyncClient` across looped calls (`list_dataset_resources` pattern).
    - Clamp user-controlled pagination/filter values before requests.
    - Build environment-dependent URLs only through `helpers/env_config.py`.
    - Register every new tool in `tools/__init__.py`.
    - Add or update tests with each behavior change.
    </do>
    <dont>
    - Do not hardcode `demo`/`prod` URLs in tool files; use `env_config.get_base_url`.
    - Do not leak raw tracebacks to MCP clients; return concise error strings.
    - Do not leave unclosed `httpx.AsyncClient` sessions.
    - Do not introduce write/mutation operations against data.gouv.fr APIs.
    - Do not bypass transport security settings in `main.py`.
    </dont>
  </patterns>

  <commit_conventions>
  - Use Conventional Commit style seen in history: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`.
  - Use `type(scope): summary` when scope matters (example: `feat(query_resource_data): ...`).
  - Breaking changes use `!` in subject (`refactor!:`) for release script detection.
  </commit_conventions>
</conventions>

<workflows>
  <new_mcp_tool>
  1. Add API logic in the appropriate `helpers/*.py` file.
  2. Create `tools/<tool_name>.py` with `register_<tool_name>_tool(mcp: FastMCP)`.
  3. Return structured, readable string output (headings + concise rows).
  4. Register tool in `tools/__init__.py`.
  5. Add tests (helper-level required; tool-level when behavior is complex).
  6. Run `uv run pytest -q`.
  7. Run lint/format/type commands from `<commands>`.
  8. Review diff for accidental URL/env/security regressions.
  </new_mcp_tool>

  <bug_fix>
  1. Reproduce via failing test or targeted command.
  2. Fix the smallest boundary owning the bug (`helpers/` first, then `tools/`).
  3. Add/adjust regression test.
  4. Run targeted tests, then full `uv run pytest -q`.
  5. Run lint + type checks.
  </bug_fix>

  <release>
  1. Ensure on `main` with clean working tree and synced remote.
  2. Run `./tag_version.sh <version> --dry-run`.
  3. Validate generated changelog chunk.
  4. Run `./tag_version.sh <version>`.
  5. Confirm tag + GitHub release creation.
  </release>
</workflows>

<boundaries>
  <forbidden>
  DO NOT modify under any circumstances without explicit instruction:
  - `.env`, `.env.*`, secret/token/key files.
  - Git internals under `.git/`.
  - Any production infrastructure outside this repository.
  </forbidden>

  <gated>
  Modify only with explicit human approval:
  - `main.py` (transport security, host/origin policy, runtime binding).
  - `helpers/env_config.py` (API target environments).
  - `Dockerfile`, `docker-compose.yml` (runtime/deployment behavior).
  - `.circleci/config.yml`, `.pre-commit-config.yaml` (quality gates).
  - `pyproject.toml`, `uv.lock` (dependency and runtime contract).
  - `tag_version.sh`, `CHANGELOG.md` (release automation/history).
  </gated>

  <zone_map>
  | Path | Zone |
  |---|---|
  | `.circleci/config.yml` | Supervised |
  | `.cursor/rules/*.md` | Autonomous |
  | `.env.example` | Autonomous |
  | `.gitignore` | Autonomous |
  | `.pre-commit-config.yaml` | Supervised |
  | `CHANGELOG.md` | Supervised |
  | `Dockerfile` | Supervised |
  | `LICENSE` | Autonomous |
  | `README.md` | Autonomous |
  | `docker-compose.yml` | Supervised |
  | `helpers/datagouv_api_client.py` | Autonomous |
  | `helpers/tabular_api_client.py` | Autonomous |
  | `helpers/metrics_api_client.py` | Autonomous |
  | `helpers/crawler_api_client.py` | Autonomous |
  | `helpers/env_config.py` | Supervised |
  | `main.py` | Supervised |
  | `pyproject.toml` | Supervised |
  | `tag_version.sh` | Supervised |
  | `tests/*.py` | Autonomous |
  | `tools/*.py` | Autonomous |
  | `uv.lock` | Supervised |
  | `CLAUDE.md` | Supervised |
  | `agents.md` | Supervised |
  | `.codex/skills/*` | Supervised |
  </zone_map>

  <safety_checks>
  Before any destructive or high-risk operation (delete/overwrite/release/tag):
  1. State exact command and target files.
  2. State rollback path and failure mode.
  3. Wait for explicit confirmation.
  </safety_checks>
</boundaries>

<troubleshooting>
  <known_issues>
  | Symptom | Cause | Fix |
  |---|---|---|
  | `Error: Invalid MCP_PORT environment variable` | `MCP_PORT` is non-numeric | Set integer port, e.g. `MCP_PORT=8000` |
  | `Metrics API is not available in the demo environment` | `DATAGOUV_ENV=demo` | Use `DATAGOUV_ENV=prod` for `get_metrics` |
  | `Resource ... not available via Tabular API` | Non-tabular/unsupported resource or 404 | Use `download_and_parse_resource` |
  | Frequent HTTP 404 on dataset/resource IDs | Stale or invalid ID | Re-run search/list tools to discover valid IDs |
  | `421 Invalid Host header` or host rejection | Host/origin not in transport security allow-list | Use localhost allowed host or update `main.py` with approval |
  | `docker compose` demo env has no effect | `docker-compose.yml` uses legacy `DATAGOUV_API_ENV`; code reads `DATAGOUV_ENV` | Set `DATAGOUV_ENV` explicitly when running compose or update compose file with approval |
  | Integration tests fail intermittently | External API/network instability | Retry once; if persistent, run health test + targeted failing tests |
  </known_issues>

  <recovery_patterns>
  1. Read full error and note failing URL/ID.
  2. Verify env vars: `DATAGOUV_ENV`, `MCP_HOST`, `MCP_PORT`.
  3. Re-sync dependencies: `uv sync --frozen`.
  4. Run a local baseline: `uv run pytest tests/test_health_endpoint.py -q`.
  5. Run focused tests, then full suite.
  6. If blocked, report exact command, output snippet, and suspected boundary.
  </recovery_patterns>
</troubleshooting>

<environment>
- Harness: Codex coding agent in terminal.
- Filesystem scope: full repository read/write.
- Network access: enabled (required for integration tests and external APIs).
- Tool access: shell, git, Python/uv tooling.
- Human interaction model: synchronous chat with explicit approval for gated changes.
</environment>

<skills>
Canonical path: `.codex/skills/` (symlinked at `.claude/skills` and `.agents/skills`).

Available project skills:
- `mcp-tool-development.md`: Add/modify MCP tools and registration safely.
- `api-client-integration.md`: Extend helper clients with consistent async/httpx patterns.
- `testing-and-validation.md`: Execute test/lint/type workflows and regression strategy.
- `release-versioning.md`: Run controlled release/tag/changelog workflow.

Load skill files only when entering the corresponding domain.
</skills>

<memory>
  <project_decisions>
  - 2025-11-26: Use `httpx` instead of `aiohttp` for async API access and simpler maintenance.
  - 2025-11-26: Keep MCP surface read-only (remove write/edit tool paths).
  - 2026-01-13: Enable DNS rebinding protections and strict host/origin allow-lists in `main.py`.
  - 2026-01-23: Add filter/sort support to `query_resource_data` for targeted row retrieval.
  - 2026-01-15: Add `MCP_HOST` control for local-host binding and MCP security compliance.
  </project_decisions>

  <lessons_learned>
  - Full pytest suite depends on live external APIs; treat it as integration validation, not pure unit tests.
  - Stable known IDs (`TEST_DATASET_ID`, `TEST_RESOURCE_ID`) reduce flaky failure triage time.
  - Returning concise string payloads from tools is intentional for MCP client usability.
  - `.cursor/rules/overview.md` may drift; verify against code before relying on it.
  </lessons_learned>
</memory>
