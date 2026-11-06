"""Actionable filesystem diagnostics at the shared standard-library boundary."""
from pathlib import Path

import pytest

from slang.stdlib_runtime import execute_runtime_call


def _read_text(values):
    return Path(values[0]).read_text(encoding="utf-8")


def _write_text(values):
    Path(values[0]).write_text(values[1], encoding="utf-8")
    return True


def _make_directory(values):
    Path(values[0]).mkdir(parents=False, exist_ok=False)
    return True


def test_missing_file_error_suggests_checking_path(tmp_path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(RuntimeError, match="read_text failed") as caught:
        execute_runtime_call("read_text", [str(missing)], _read_text)
    message = str(caught.value)
    assert str(missing) in message
    assert "does not exist" in message
    assert "parent directory exists" in message


def test_missing_parent_on_write_is_actionable(tmp_path):
    target = tmp_path / "absent" / "output.txt"
    with pytest.raises(RuntimeError, match="write_text failed") as caught:
        execute_runtime_call("write_text", [str(target), "hello"], _write_text)
    assert "parent directory exists" in str(caught.value)


def test_existing_directory_creation_explains_conflict(tmp_path):
    directory = tmp_path / "already-here"
    directory.mkdir()
    with pytest.raises(RuntimeError, match="make_directory failed") as caught:
        execute_runtime_call("make_directory", [str(directory)], _make_directory)
    assert "already exists" in str(caught.value)


def test_successful_file_io_is_unchanged(tmp_path):
    target = tmp_path / "ok.txt"
    assert execute_runtime_call("write_text", [str(target), "hello"], _write_text) == (True, True)
    assert execute_runtime_call("read_text", [str(target)], _read_text) == (True, "hello")
