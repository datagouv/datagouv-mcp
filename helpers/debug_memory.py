"""
Debug memory diagnostics -- temporary endpoints for production investigation.
Gated behind ENABLE_DEBUG=true env var.
Uses only stdlib: tracemalloc, gc, resource.
"""

import gc
import linecache
import resource
import tracemalloc
from collections import Counter
from typing import Any

_snapshot: tracemalloc.Snapshot | None = None


def start_tracemalloc() -> None:
    if not tracemalloc.is_tracing():
        tracemalloc.start(25)


def get_memory_info() -> dict[str, Any]:
    """Current RSS, tracemalloc top allocations, GC stats, top object types."""
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = rusage.ru_maxrss / (1024 * 1024)  # macOS returns bytes, Linux returns KB
    import platform

    if platform.system() == "Linux":
        rss_mb = rusage.ru_maxrss / 1024

    result: dict[str, Any] = {
        "rss_max_mb": round(rss_mb, 2),
        "tracemalloc_tracing": tracemalloc.is_tracing(),
    }

    if tracemalloc.is_tracing():
        current, peak = tracemalloc.get_traced_memory()
        result["tracemalloc_current_mb"] = round(current / (1024 * 1024), 2)
        result["tracemalloc_peak_mb"] = round(peak / (1024 * 1024), 2)

        snapshot = tracemalloc.take_snapshot()
        snapshot = snapshot.filter_traces(
            (
                tracemalloc.Filter(False, "<frozen *>"),
                tracemalloc.Filter(False, "<unknown>"),
                tracemalloc.Filter(False, tracemalloc.__file__),
            )
        )
        top_stats = snapshot.statistics("lineno")[:20]
        result["top_allocations"] = [
            {
                "file": str(stat.traceback),
                "size_kb": round(stat.size / 1024, 1),
                "count": stat.count,
            }
            for stat in top_stats
        ]

    gc_stats = gc.get_stats()
    result["gc"] = {
        "generations": gc_stats,
        "garbage_count": len(gc.garbage),
    }

    type_counts = Counter(type(obj).__name__ for obj in gc.get_objects())
    result["top_object_types"] = type_counts.most_common(25)

    return result


def take_snapshot() -> dict[str, str]:
    """Take a tracemalloc snapshot as baseline for future diffs."""
    global _snapshot
    if not tracemalloc.is_tracing():
        return {"error": "tracemalloc is not tracing, set ENABLE_DEBUG=true"}
    _snapshot = tracemalloc.take_snapshot()
    _snapshot = _snapshot.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen *>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    return {"status": "snapshot taken"}


def get_diff() -> dict[str, Any]:
    """Compare current allocations to the last snapshot."""
    global _snapshot
    if _snapshot is None:
        return {"error": "no baseline snapshot -- call /debug/memory/snapshot first"}
    if not tracemalloc.is_tracing():
        return {"error": "tracemalloc is not tracing"}

    current = tracemalloc.take_snapshot()
    current = current.filter_traces(
        (
            tracemalloc.Filter(False, "<frozen *>"),
            tracemalloc.Filter(False, "<unknown>"),
        )
    )
    diff_stats = current.compare_to(_snapshot, "lineno")[:30]

    # Clear linecache to avoid stale data
    linecache.clearcache()

    return {
        "diff_since_snapshot": [
            {
                "file": str(stat.traceback),
                "size_diff_kb": round(stat.size_diff / 1024, 1),
                "size_kb": round(stat.size / 1024, 1),
                "count_diff": stat.count_diff,
                "count": stat.count,
            }
            for stat in diff_stats
            if stat.size_diff > 0
        ]
    }
