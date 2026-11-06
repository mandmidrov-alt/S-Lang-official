"""Actionable diagnostics for text encoding and filesystem argument mistakes."""
from pathlib import Path

import pytest

from slang.stdlib_runtime import execute_runtime_call


def _read_text(values):
    return Path(values[0]).read_text(encoding="utf-8")


def _read_lines(values):
    return Path(values[0]).read_text(encoding="utf-8").splitlines()


def _read_json(values):
    import json
    return json.loads(Path(values[0]).read_text(encoding="utf-8"))


def test_invalid_utf8_error_includes_path_and_recovery_advice(tmp_path):
    target = tmp_path / "invalid-encoding.txt"
    target.write_bytes(b"hello\xffworld")

    with pytest.raises(RuntimeError, match="not valid UTF-8") as caught:
        execute_runtime_call("read_text", [str(target)], _read_text)

    message = str(caught.value)
    assert str(target) in message
    assert "byte offset 5" in message
    assert "Save the file as UTF-8" in message


def test_invalid_utf8_is_reported_for_json_file_reads(tmp_path):
    target = tmp_path / "invalid.json"
    target.write_bytes(b'{"name":"\xff"}')

    with pytest.raises(RuntimeError, match="read_json failed") as caught:
        execute_runtime_call("read_json", [str(target)], _read_json)

    assert str(target) in str(caught.value)
    assert "not valid UTF-8" in str(caught.value)


def test_wrong_filesystem_path_type_has_actionable_message():
    with pytest.raises(RuntimeError, match="expected a text file path") as caught:
        execute_runtime_call("read_text", [123], _read_text)
    assert "check the argument type" in str(caught.value)


def test_valid_utf8_file_read_remains_unchanged(tmp_path):
    target = tmp_path / "valid.txt"
    target.write_text("Kamchatka — текст", encoding="utf-8")
    assert execute_runtime_call("read_text", [str(target)], _read_text) == (True, "Kamchatka — текст")
