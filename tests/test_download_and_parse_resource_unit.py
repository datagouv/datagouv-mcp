import gzip

from tools import download_and_parse_resource


def test_detect_file_format_handles_compressed_json() -> None:
    assert (
        download_and_parse_resource._detect_file_format("sample.json.gz", None)
        == "json"
    )
    assert (
        download_and_parse_resource._detect_file_format("sample.jsonl.gz", None)
        == "json"
    )
    assert (
        download_and_parse_resource._detect_file_format("sample.ndjson.gz", None)
        == "json"
    )


def test_detect_file_format_prefers_extensions_over_content_type() -> None:
    assert (
        download_and_parse_resource._detect_file_format(
            "sample.csv", "application/json"
        )
        == "csv"
    )


def test_parse_csv_detects_semicolon_delimiter() -> None:
    content = "name;age\nAlice;30\nBob;40\n".encode()
    rows = download_and_parse_resource._parse_csv(content)
    assert rows == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "40"}]


def test_parse_csv_supports_gzip() -> None:
    raw = "name,age\nAlice,30\n".encode()
    rows = download_and_parse_resource._parse_csv(gzip.compress(raw), is_gzipped=True)
    assert rows == [{"name": "Alice", "age": "30"}]


def test_parse_json_supports_array_object_and_jsonl() -> None:
    array_rows = download_and_parse_resource._parse_json(b'[{"a":1},{"a":2}]')
    assert array_rows == [{"a": 1}, {"a": 2}]

    object_rows = download_and_parse_resource._parse_json(b'{"a":1}')
    assert object_rows == [{"a": 1}]

    jsonl_rows = download_and_parse_resource._parse_json(
        b'{"a":1}\n{"a":2}\nnot-json\n{"a":3}\n'
    )
    assert jsonl_rows == [{"a": 1}, {"a": 2}, {"a": 3}]
