"""Shared pytest configuration."""

import os

import pytest


def _integration_enabled() -> bool:
    value = os.getenv("RUN_INTEGRATION_TESTS", "")
    return value.strip().lower() in {"1", "true", "yes"}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless explicitly enabled."""
    if _integration_enabled():
        return

    skip_integration = pytest.mark.skip(
        reason="integration test (set RUN_INTEGRATION_TESTS=1 to run)"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
