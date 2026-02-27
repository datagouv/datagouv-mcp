from helpers import formatting


def test_format_file_size_scales_units() -> None:
    assert formatting.format_file_size(500) == "500 B"
    assert formatting.format_file_size(2048) == "2.0 KB"
    assert formatting.format_file_size(3 * 1024 * 1024) == "3.0 MB"
    assert formatting.format_file_size(5 * 1024 * 1024 * 1024) == "5.0 GB"


def test_truncate_text_keeps_short_values() -> None:
    assert formatting.truncate_text("hello", 10) == "hello"


def test_truncate_text_adds_ellipsis_for_long_values() -> None:
    assert formatting.truncate_text("abcdefghij", 5) == "abcde..."
