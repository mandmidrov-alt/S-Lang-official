from slang.stdlib import copy_file, make_directories, move_file, read_text, write_text
from slang.stdlib.catalog import entries


def test_copy_file(tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "copy.txt"
    write_text(str(source), "payload")
    assert copy_file(str(source), str(target)) is True
    assert read_text(str(source)) == "payload"
    assert read_text(str(target)) == "payload"


def test_move_file(tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "moved.txt"
    write_text(str(source), "payload")
    assert move_file(str(source), str(target)) is True
    assert not source.exists()
    assert read_text(str(target)) == "payload"


def test_make_directories(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    assert make_directories(str(nested)) is True
    assert nested.is_dir()


def test_catalog_exposes_file_management_operations():
    catalog = {entry["name"]: entry for entry in entries()}
    for name in ("copy_file", "move_file", "make_directories"):
        assert catalog[name]["effect"] == "IO"
        assert catalog[name]["module"] == "slang.stdlib.files"
