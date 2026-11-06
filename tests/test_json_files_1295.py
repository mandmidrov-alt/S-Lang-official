from pathlib import Path
from slang.stdlib.files import read_json, write_json
from slang.semantic import infer

def test_json_file_round_trip(tmp_path):
    path = tmp_path / "config.json"
    value = {"name": "S-Lang", "items": [1, True, None]}
    assert write_json(str(path), value) is True
    assert read_json(str(path)) == value

def test_json_file_is_human_readable(tmp_path):
    path = tmp_path / "config.json"
    write_json(str(path), {"b": 2, "a": 1})
    assert path.read_text(encoding="utf-8") == '{\n  "a": 1,\n  "b": 2\n}\n'

def test_unicode_round_trip(tmp_path):
    path = tmp_path / "config.json"
    value = {"тест": "значение"}
    write_json(str(path), value)
    assert read_json(str(path)) == value

def test_invalid_json_fails(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        read_json(str(path))

def test_public_file_api():
    import slang.stdlib.files as files
    assert callable(files.read_json) and callable(files.write_json)
