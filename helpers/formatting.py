"""Shared formatting helpers for tool responses."""


def format_file_size(size_bytes: int) -> str:
    """Format a size in bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def truncate_text(value: str, max_len: int) -> str:
    """Truncate text to max_len and append ellipsis when needed."""
    if len(value) <= max_len:
        return value
    return f"{value[:max_len]}..."
