<activation>
Use this protocol only when at least one condition is true:
1. Task spans 2+ domains (`tools/` + `helpers/` + infra/docs).
2. Task can be parallelized across non-overlapping file sets.
3. Reviewer separation is needed for high-risk changes.

Default for small changes: single-agent execution using `CLAUDE.md`.
</activation>

<roles>
| Role | Model Tier | Responsibility | Hard Boundary |
|---|---|---|---|
| Orchestrator | Frontier | Decompose task, assign scopes, integrate outputs | Does not write production code directly |
| Implementer | Mid-tier | Modify code/tests/docs within assigned scope | Does not change architecture/contracts without approval |
| Reviewer | Frontier | Validate correctness, safety, regressions | Does not implement fixes directly |
| Specialist | Any | Domain-only execution (release/security/testing) | Operates only in declared domain |
</roles>

<delegation_protocol>
1. ANALYZE: classify task risk (low/medium/high) and touched boundaries.
2. DECOMPOSE: split into atomic units by file ownership.
3. CLASSIFY: route units to Implementer or Specialist.
4. PLAN: define ordering and parallel groups.
5. DELEGATE: send task packet using `<task_format>`.
6. MONITOR: require concise progress + blockers.
7. INTEGRATE: merge outputs; resolve overlap.
8. REVIEW: run quality gate (tests/lint/type + boundary compliance).
</delegation_protocol>

<task_format>
## Task: [short title]

**Objective**: [single done-condition sentence]

**Context**:
- Files to read: [exact paths]
- Files to modify: [exact paths]
- Files to create: [exact paths]
- Interfaces to preserve: [functions/types/commands]

**Acceptance criteria**:
- [ ] Behavior updated as requested
- [ ] `uv run pytest -q` passes (or scoped test command)
- [ ] `uv run ruff check --select I .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run ty check` passes

**Constraints**:
- Do NOT modify: [out-of-scope files]
- Approval required for: `main.py`, `helpers/env_config.py`, CI, Docker, release scripts, dependencies
- Time box: [estimate]

**Handoff**:
- Diff summary
- Commands executed + results
- Open risks/questions
</task_format>

<state_machine>
PENDING -> ASSIGNED -> IN_PROGRESS -> REVIEW -> APPROVED -> DONE

Additional transitions:
- `IN_PROGRESS -> BLOCKED`: include blocker, attempts, needed input.
- `REVIEW -> REJECTED`: include exact failing checks and fix guidance.
- `BLOCKED -> IN_PROGRESS`: after unblock confirmation.
- `BLOCKED` older than 30 min -> escalate to human.
</state_machine>

<parallel_execution>
Safe to parallelize:
- Distinct file sets (for example: docs + tests, or helper A + helper B with no shared imports).
- Independent test-writing tasks after interface freeze.
- Skills/context updates separate from runtime code.

Must serialize:
- Any change touching `main.py`.
- Dependency changes (`pyproject.toml`, `uv.lock`).
- Release operations (`tag_version.sh`, tags/releases).
- Shared-file edits (`tools/__init__.py`, `helpers/env_config.py`).

Conflict protocol:
1. Detect overlaps before assignment.
2. Prioritize higher-risk/contract-owner task.
3. Wait, then rebase/reapply lower-priority task.
4. Re-run validation commands.
</parallel_execution>

<escalation>
Escalate immediately when:
- Security policy/transport boundary change is required.
- Public tool behavior must break backward compatibility.
- CI/release pipeline semantics must change.
- Confidence in assumptions is below 70%.

Escalation template:
- `ESCALATION`: [one-line blocker]
- `Context`: [current objective + files]
- `Blocked by`: [specific issue]
- `Options`: [1..N with tradeoffs]
- `Recommendation`: [best path + why]
- `Delay impact`: [cost of waiting]
</escalation>

<repo_specific_constraints>
- Forbidden: `.env`, `.env.*`, secret files, `.git/` internals.
- Gated approval: `main.py`, `helpers/env_config.py`, `.circleci/config.yml`, `.pre-commit-config.yaml`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`, `tag_version.sh`, `CHANGELOG.md`, context files.
- Required pre-handoff checks unless explicitly waived:
  - `uv run pytest -q`
  - `uv run ruff check --select I .`
  - `uv run ruff format --check .`
  - `uv run ty check`
</repo_specific_constraints>
