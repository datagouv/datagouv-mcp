# Skill Registry

Last updated: 2026-02-26

| Skill | File | Triggers | Priority |
|---|---|---|---|
| MCP Tool Development | `mcp-tool-development.md` | `tool`, `@mcp.tool`, `register_tools`, `FastMCP`, new endpoint formatting | Core |
| API Client Integration | `api-client-integration.md` | `httpx`, `helpers/`, API wrapper, timeout, session reuse | Core |
| Testing and Validation | `testing-and-validation.md` | `pytest`, `ruff`, `ty`, regression, flaky integration test | Core |
| Release and Versioning | `release-versioning.md` | `tag`, `release`, `CHANGELOG`, `tag_version.sh`, conventional commits | Extend |

## Skill Gap Analysis

High priority gaps (recommended next):
- [ ] `security-review.md` - Transport security, host/origin policy, secret-handling checks.
- [ ] `dependency-upgrades.md` - Safe updates for `pyproject.toml`/`uv.lock` with rollback strategy.

Medium priority gaps:
- [ ] `deployment-operations.md` - Runtime deployment checklist beyond local Docker/CircleCI.
- [ ] `performance-diagnostics.md` - Latency profiling for external API-bound tools.
- [ ] `code-review-checklist.md` - Standardized severity-based review rubric.

Lower priority gaps:
- [ ] `documentation-maintenance.md` - Keep README and `.cursor/rules` synchronized with code.
