# Production Readiness Roadmap

This roadmap tracks the remaining work to bring `datagouv-mcp` from stable MVP to fully production-grade operations.

## Current state

- Core feature set is complete for read-only dataset/dataservice exploration.
- Unit and integration tests are now separated, which improves CI determinism.
- Major operational defaults are in place (`/health`, environment wiring, logging level control).

## Priority 1: Observability and operations

1. Add structured request logging for tool invocations.
   - Include tool name, latency, upstream API status, and failure category.
   - Exclude sensitive payload content from logs.
2. Expose minimal service metrics endpoint.
   - Request count, error count, upstream timeout count, p95 latency.
3. Add runbook documentation for incidents.
   - Upstream API outage handling.
   - Degraded mode behavior and operator checklist.

## Priority 2: Reliability hardening

1. Add retry/backoff policy for transient upstream failures.
   - Scope retries to safe GET calls.
   - Enforce strict timeout budgets.
2. Add circuit-breaker style protection for repeated upstream failures.
3. Add payload size safeguards for large tool responses.
   - Truncate rows/fields consistently.
   - Return explicit guidance when truncation occurs.

## Priority 3: API and UX consistency

1. Standardize error messages across all tools.
   - Distinguish validation errors, not-found, upstream errors, and internal errors.
2. Formalize tool response schemas.
   - Keep text output for LLM UX, but define stable machine-readable structure internally.
3. Add end-to-end smoke tests for each tool against a fixed fixture dataset/resource set.

## Release gate checklist

- [ ] Lint/type/unit tests green on CI.
- [ ] Integration tests green on `main`.
- [ ] Incident runbook reviewed by maintainers.
- [ ] Tagged release validated on pre-production.
- [ ] Backward compatibility checked for tool names and parameters.
