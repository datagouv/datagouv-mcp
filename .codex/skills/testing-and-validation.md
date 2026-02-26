---
name: testing-and-validation
description: Use for any code change requiring confidence checks, including pytest execution strategy, lint/format/type gates, flaky integration triage, and pre-merge validation in this repository.
prerequisites: uv, network access for integration tests
---

# Testing and Validation

<purpose>
Run the fastest reliable validation sequence for this codebase and add regression coverage where behavior changes.
</purpose>

<context>
- Test suite is mostly integration-style and hits live external APIs.
- `tests/test_health_endpoint.py` is local-only and fastest smoke test.
- CI runs: import-sort lint, format check, and type check (`ty`) plus pytest on `main`.
- Quality commands are copy-pasteable from README and validated locally.
</context>

<procedure>
1. Decide scope:
- Small/local change -> run targeted test file first.
- Behavior/API change -> run full suite.
2. Execute quick baseline: `uv run pytest tests/test_health_endpoint.py -q`.
3. Run changed-domain tests (example: `uv run pytest tests/test_tabular_api.py -q`).
4. Run full tests: `uv run pytest -q`.
5. Run lint/format/type checks:
- `uv run ruff check --select I .`
- `uv run ruff format --check .`
- `uv run ty check`
6. If failures are external-network related, retry once and capture exact failing endpoint/ID.
7. Add regression tests for any bug fix before handoff.
</procedure>

<patterns>
<do>
- Prefer deterministic assertions on structure/keys over brittle full-text comparisons.
- Use fixtures/env vars (`TEST_DATASET_ID`, `TEST_RESOURCE_ID`, `RESOURCE_ID`) for stable IDs.
- Keep helper tests focused on return shapes and error behavior.
- Use `pytest.mark.asyncio` for async helper tests.
</do>
<dont>
- Don’t treat network-dependent failures as code regressions without one retry.
- Don’t skip lint/type gates after test pass -> CI can still fail.
- Don’t add tests that depend on private credentials.
- Don’t rely only on manual MCP client checks when automated test is possible.
</dont>
</patterns>

<examples>
Example: Full local pre-PR gate
```bash
uv run pytest -q
uv run ruff check --select I .
uv run ruff format --check .
uv run ty check
```

Example: Focused loop for tabular logic
```bash
uv run pytest tests/test_tabular_api.py -q
uv run pytest tests/test_health_endpoint.py -q
```
</examples>

<troubleshooting>
| Symptom | Cause | Fix |
|---|---|---|
| Sporadic test failures on API tests | External service/network variance | Retry once, then inspect endpoint status and payload shape |
| `pytest` passes but CI fails | Missed lint/format/type gates | Run full quality command set locally |
| `test_get_metrics*` fails in demo mode | Metrics endpoint is prod-only | Run with `DATAGOUV_ENV=prod` |
| Slow feedback loop | Running full suite for tiny change | Start with targeted file + smoke test, then full suite before handoff |
</troubleshooting>

<references>
- `tests/test_health_endpoint.py`: local-only smoke test.
- `tests/test_datagouv_api.py`: dataset/dataservice helper integration tests.
- `tests/test_tabular_api.py`: tabular query/filter/sort behavior.
- `.circleci/config.yml`: CI gate commands.
</references>
