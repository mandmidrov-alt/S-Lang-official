from slang.stdlib import json_get, json_has, json_set
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries

def test_json_get_reads_nested_values_and_default():
    value = {"user": {"name": "D", "tags": ["a", "b"]}}
    assert json_get(value, "user.name", None) == "D"
    assert json_get(value, "user.tags.1", None) == "b"
    assert json_get(value, "user.missing", "fallback") == "fallback"

def test_json_has_checks_nested_paths():
    value = {"user": {"name": "D"}}
    assert json_has(value, "user.name") is True
    assert json_has(value, "user.missing") is False

def test_json_set_returns_updated_copy_without_mutating_input():
    value = {"user": {"name": "D"}}
    updated = json_set(value, "user.name", "X")
    assert updated == {"user": {"name": "X"}}
    assert value == {"user": {"name": "D"}}

def test_json_set_can_create_nested_paths():
    assert json_set({}, "settings.theme.mode", "dark") == {"settings": {"theme": {"mode": "dark"}}}

def test_public_json_path_api():
    assert get("json_get") is not None and get("json_has") is not None and get("json_set") is not None
    assert {"json_get", "json_has", "json_set"} <= set(signatures())
    assert {"json_get", "json_has", "json_set"} <= {e["name"] for e in entries()}
