import json
import subprocess
import sys

from slang.stdlib.modules import MODULES, module_entries, modules


def test_standard_library_has_stable_module_taxonomy():
    rows = modules()
    assert [row["name"] for row in rows] == sorted(MODULES)
    assert all(row["module"] == f"slang.stdlib.{row['name']}" for row in rows)
    assert all(row["function_count"] == len(row["functions"]) for row in rows)
    assert all(row["functions"] == sorted(row["functions"]) for row in rows)


def test_module_entries_are_partitioned_by_public_module():
    all_names = []
    for name in MODULES:
        rows = module_entries(name)
        assert all(row["module"] == f"slang.stdlib.{name}" for row in rows)
        all_names.extend(row["name"] for row in rows)
    assert len(all_names) == len(set(all_names))


def test_cli_can_inspect_one_standard_library_module():
    proc = subprocess.run(
        [sys.executable, "-m", "slang.cli", "stdlib", "math"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["module"] == "math"
    assert payload["count"] >= 5
    assert all(row["module"] == "slang.stdlib.math" for row in payload["entries"])


def test_datetime_is_a_public_standard_library_module():
    from slang.stdlib.catalog import entries

    datetime_entries = [row for row in entries() if row["module"] == "slang.stdlib.datetime"]
    assert len(datetime_entries) == 15
    assert "datetime" in MODULES
    assert len(module_entries("datetime")) == 15
    assert sum(row["function_count"] for row in modules()) == len(entries()) == 277


def test_catalogued_text_file_functions_validate_and_execute(tmp_path):
    from slang.core import parse_file, validate, run

    (tmp_path / "input.txt").write_text("hello", encoding="utf-8")
    source = tmp_path / "main.sl"
    source.write_text(
        'let content = read_text("input.txt")\n'
        'let saved = write_text("output.txt", content)\n'
        'let appended = append_text("output.txt", " world")\n',
        encoding="utf-8",
    )
    program = parse_file(source)
    validate(program)
    run(program)
    assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "hello world"


def test_datetime_standard_import_is_accepted(tmp_path):
    from slang.core import parse_file, validate

    source = tmp_path / "main.sl"
    source.write_text(
        'import std.datetime\n'
        'let today = today_utc()\n'
        'let parsed = parse_datetime("2026-10-30T10:00:00Z", "")\n',
        encoding="utf-8",
    )
    validate(parse_file(source))
