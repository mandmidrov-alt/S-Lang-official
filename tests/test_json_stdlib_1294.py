from slang.stdlib import json_parse, json_stringify, json_pretty
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries

def test_pretty_is_readable_and_sorted():
    assert json_pretty({"b": 2, "a": 1}) == '{\n  "a": 1,\n  "b": 2\n}'

def test_pretty_round_trips():
    value = {"name": "S-Lang", "items": [1, True, None]}
    assert json_parse(json_pretty(value)) == value

def test_pretty_preserves_unicode():
    assert '"тест"' in json_pretty({"тест": "значение"})

def test_registry_and_catalog():
    assert get("json_pretty") is not None
    assert "json_pretty" in signatures()
    assert any(e["name"] == "json_pretty" for e in entries())

def test_compact_and_pretty_differ():
    value = {"a": 1, "b": 2}
    assert json_stringify(value) != json_pretty(value)
