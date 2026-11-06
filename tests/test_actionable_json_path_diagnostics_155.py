import pytest

from slang.stdlib.json import set_path
from slang.core import parse, run, validate


def _run(source: str):
    program = parse(source)
    validate(program)
    run(program)
    return program


def test_json_set_scalar_intermediate_names_path_and_suggests_structure_check():
    with pytest.raises(TypeError) as error:
        set_path(4, "profile.name", "Ada")
    message = str(error.value)
    assert "profile.name" in message
    assert "scalar" in message
    assert "object or array" in message or "structure" in message


def test_json_set_negative_array_index_is_actionable():
    with pytest.raises((ValueError, RuntimeError)) as error:
        set_path(["a"], "-1", "b")
    assert "negative array index" in str(error.value)
    assert "start at 0" in str(error.value)


def test_json_set_non_numeric_array_index_is_actionable():
    with pytest.raises((ValueError, RuntimeError)) as error:
        set_path(["a"], "first", "b")
    assert "array index" in str(error.value)
    assert "whole-number index" in str(error.value)


def test_json_get_missing_path_keeps_default_semantics():
    program = _run('let value = json_get(json_parse("{\\"profile\\": {}}"), "profile.name", "unknown")\n')
    assert program._bindings["value"] == "unknown"


def test_json_has_missing_path_remains_explicit_existence_check():
    program = _run('let value = json_has(json_parse("{\\"profile\\": {}}"), "profile.name")\n')
    assert program._bindings["value"] is False
