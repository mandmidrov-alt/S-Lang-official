from slang.stdlib import append_text, read_lines, read_text, remove_file, write_text
from slang.stdlib.catalog import entries


def test_text_file_roundtrip(tmp_path):
    path = tmp_path / "sample.txt"
    assert write_text(str(path), "alpha\nβeta\n") is True
    assert read_text(str(path)) == "alpha\nβeta\n"
    assert read_lines(str(path)) == ["alpha", "βeta"]


def test_append_text(tmp_path):
    path = tmp_path / "append.txt"
    write_text(str(path), "first")
    assert append_text(str(path), "\nsecond") is True
    assert read_text(str(path)) == "first\nsecond"


def test_remove_file(tmp_path):
    path = tmp_path / "remove.txt"
    write_text(str(path), "x")
    assert path.is_file()
    assert remove_file(str(path)) is True
    assert not path.exists()


def test_empty_lines_are_preserved_as_line_structure(tmp_path):
    path = tmp_path / "empty.txt"
    write_text(str(path), "a\n\nb\n")
    assert read_lines(str(path)) == ["a", "", "b"]


def test_catalog_exposes_io_operations():
    catalog = {entry["name"]: entry for entry in entries()}
    for name in ("read_text", "write_text", "append_text", "read_lines", "remove_file"):
        assert catalog[name]["effect"] == "IO"
        assert catalog[name]["module"] == "slang.stdlib.files"
