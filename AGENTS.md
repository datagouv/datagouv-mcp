# AGENTS.md

## Purpose

Guidance for AI/code agents working on `datagouv-mcp`.

## Project invariants

- This server is read-only: do not add mutation/write capabilities to upstream data.gouv.fr APIs.
- Transport is Streamable HTTP only (`/mcp`), with `/health` for probes.
- Prefer simple, explicit behavior over abstraction-heavy refactors.

## Code layout

- `main.py`: server bootstrap and transport security.
- `tools/`: MCP tool handlers and response formatting.
- `helpers/`: upstream API clients and shared utility helpers.
- `tests/`: unit tests + integration tests.

## Testing policy

- Default local/CI run is deterministic unit tests:
  - `uv run pytest`
- Integration tests call live remote APIs and are opt-in:
  - `RUN_INTEGRATION_TESTS=1 uv run pytest -m integration`
- Keep network tests marked with `@pytest.mark.integration`.

## Change expectations

- Preserve tool names and parameters for backward compatibility.
- If behavior changes, update `README.md` and add/adjust tests in the same change.
- Keep error messages actionable and specific.

## Release hygiene

- Run lint + format + type checks:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run ty check`
- Update `CHANGELOG.md` and `ROADMAP.md` when change scope warrants it.
