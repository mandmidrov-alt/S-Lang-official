"""Semantic parity checks for record collection pipelines across execution engines."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(tmp_path, source: str, *, native: bool) -> list[str]:
    path = tmp_path / ("native.sl" if native else "interpreter.sl")
    path.write_text(source, encoding="utf-8")
    if native:
        executable = tmp_path / "native_program"
        build = subprocess.run(
            [sys.executable, "-m", "slang.cli", "build", str(path), "-o", str(executable), "--backend", "native"],
            cwd=ROOT, text=True, capture_output=True, timeout=90,
        )
        assert build.returncode == 0, f"native build failed\n{build.stderr}"
        command = [str(executable)]
    else:
        command = [sys.executable, "-m", "slang.cli", "run", str(path)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, (
        f"{'native' if native else 'interpreter'} execution failed\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def assert_engine_parity(tmp_path, source: str) -> None:
    assert execute(tmp_path, source, native=True) == execute(tmp_path, source, native=False)


def test_numeric_record_pipeline_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Person:
    name: Text
    age: Number
let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27), Person("Max", 42)]
adults = people where age >= 18
ages = adults map age
ordered = ages sort by item asc
total = ordered reduce 0 with acc + item
show total
''')


def test_boolean_field_filter_and_numeric_projection_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Person:
    name: Text
    active: Boolean
    score: Number
let people = [Person("Ada", true, 91), Person("Bob", false, 88), Person("Lin", true, 95)]
selected = people where row.active == true
scores = selected map row.score
total = scores sum item
show total
''')


def test_text_projection_sort_reduce_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15), Person("Eve", 20)]
selected = people where row.age >= 20
ordered = selected map row.label
ordered = ordered sort by item asc
joined = ordered reduce "" with acc + item
show joined
''')


def test_duplicate_numeric_sort_keys_and_post_sort_filter_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number
let people = [Person("first", 20, 3), Person("second", 10, 4), Person("third", 20, 5), Person("fourth", 10, 6)]
ordered = people sort by row.age asc
selected = ordered where row.age == 20
scores = selected map row.score
total = scores sum item
show total
''')


def test_repeated_filter_and_reassignment_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number
let people = [Person("Ada", 36, 91), Person("Bob", 15, 88), Person("Lin", 27, 95), Person("Max", 42, 72), Person("Eve", 20, 90)]
selected = people where age >= 18
selected = selected where score >= 90
selected = selected where age < 40
ages = selected map row.age
ages = ages sort by item asc
total = ages reduce 0 with acc + item
show total
''')


def test_repeated_sort_is_stable_and_preserves_reassignment_parity(tmp_path):
    source = '''
record Person:
    id: Number
    group: Number
    score: Number
let people = [Person(1, 1, 10), Person(2, 1, 20), Person(3, 2, 15), Person(4, 1, 20)]
ordered = people sort by score desc
ordered = ordered sort by group asc
ids = ordered map id
show ids
'''
    assert execute(tmp_path, source, native=True) == ['2', '4', '1', '3']
    assert execute(tmp_path, source, native=False) == ['[2, 4, 1, 3]']


def test_empty_nested_projection_count_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Address:
    city: Text
    code: Number
record Person:
    name: Text
    address: Address
let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20))]
selected = people where row.address.code > 100
codes = selected map row.address.code
counted = codes count
show counted
''')


def test_empty_nested_projection_reduce_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
record Address:
    city: Text
    code: Number
record Person:
    name: Text
    address: Address
let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20))]
selected = people where row.address.code > 100
codes = selected map row.address.code
joined = codes reduce 0 with acc + item
show joined
''')


def test_repeated_assignment_between_map_sort_and_reduce_parity(tmp_path):
    assert_engine_parity(tmp_path, '''
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
