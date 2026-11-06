"""Interpreter regressions for collection stages separated by type-changing maps."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_interpreter(tmp_path, source):
    program = tmp_path / "program.sl"
    program.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", str(program)],
        cwd=ROOT, text=True, capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def test_filter_after_record_to_number_map_uses_mapped_items(tmp_path):
    output = run_interpreter(tmp_path, '''
record Person:
    name: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15), Person("Eve", 20)]
values = people where age >= 18
values = values map age * 2
values = values where item >= 50
result = values reduce 0 with acc + item
show result
''')
    assert output == ["126"]


def test_filter_after_map_and_sort_keeps_stage_order(tmp_path):
    output = run_interpreter(tmp_path, '''
record Person:
    name: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15), Person("Eve", 20)]
values = people where age >= 18
values = values map age * 2
values = values sort by item desc
values = values where item >= 50
result = values reduce 0 with acc + item
show result
''')
    assert output == ["126"]


def test_two_stable_sorts_with_in_place_rebinding_keep_order(tmp_path):
    output = run_interpreter(tmp_path, '''
record Person:
    name: Text
    group: Number
    score: Number
let people = [Person("first", 1, 10), Person("second", 1, 20), Person("third", 2, 15), Person("fourth", 1, 20)]
ordered = people sort by score desc
ordered = ordered sort by group asc
names = ordered map name
joined = names reduce "" with acc + item + ","
show joined
''')
    assert output == ["second,fourth,first,third,"]
