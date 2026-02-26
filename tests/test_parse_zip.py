"""Tests for ZIP parsing in download_and_parse_resource."""

import io
import zipfile

import pytest

from tools.download_and_parse_resource import _parse_zip


def _make_zip(files: dict[str, str]) -> bytes:
    """Create an in-memory ZIP archive from a dict of {filename: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestParseZip:
    def test_zip_with_csv(self):
        csv_content = "name;age\nAlice;30\nBob;25\n"
        data = _make_zip({"data.csv": csv_content})

        rows, filename = _parse_zip(data)

        assert filename == "data.csv"
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"

    def test_zip_with_json(self):
        json_content = '[{"city": "Paris"}, {"city": "Lyon"}]'
        data = _make_zip({"data.json": json_content})

        rows, filename = _parse_zip(data)

        assert filename == "data.json"
        assert len(rows) == 2
        assert rows[0]["city"] == "Paris"

    def test_zip_with_jsonl(self):
        jsonl_content = '{"id": 1}\n{"id": 2}\n'
        data = _make_zip({"records.jsonl": jsonl_content})

        rows, filename = _parse_zip(data)

        assert filename == "records.jsonl"
        assert len(rows) == 2

    def test_zip_picks_first_supported_file_alphabetically(self):
        data = _make_zip(
            {
                "readme.txt": "ignore me",
                "b_data.csv": "x\n1\n",
                "a_data.csv": "x\n2\n",
            }
        )

        rows, filename = _parse_zip(data)

        assert filename == "a_data.csv"

    def test_zip_ignores_macosx_metadata(self):
        data = _make_zip(
            {
                "__MACOSX/._data.csv": "garbage",
                "data.csv": "col\nval\n",
            }
        )

        rows, filename = _parse_zip(data)

        assert filename == "data.csv"
        assert len(rows) == 1

    def test_zip_with_no_supported_files_raises(self):
        data = _make_zip({"readme.txt": "hello", "image.png": "bytes"})

        with pytest.raises(ValueError, match="ZIP contains no supported file"):
            _parse_zip(data)

    def test_empty_zip_raises(self):
        data = _make_zip({})

        with pytest.raises(ValueError, match="ZIP contains no supported file"):
            _parse_zip(data)

    def test_zip_with_nested_csv(self):
        data = _make_zip({"subdir/data.csv": "a,b\n1,2\n"})

        rows, filename = _parse_zip(data)

        assert filename == "subdir/data.csv"
        assert len(rows) == 1
        assert rows[0]["a"] == "1"
