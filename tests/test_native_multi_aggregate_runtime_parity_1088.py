"""Native/interpreter parity for multi-aggregates over materialized pipelines."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def execute(tmp_path, source, native):
    source_path = tmp_path / ("native.sl" if native else "interpreter.sl")
    source_path.write_text(source, encoding="utf-8")
    if native:
        executable = tmp_path / "native_multi_aggregate"
        build = subprocess.run(
            [sys.executable, "-m", "slang.cli", "build", str(source_path), "-o", str(executable), "--backend", "native"],
            cwd=ROOT, text=True, capture_output=True, timeout=90,
        )
        assert build.returncode == 0, build.stderr
        command = [str(executable)]
    else:
        command = [sys.executable, "-m", "slang.cli", "run", str(source_path)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def assert_parity(tmp_path, source, expected):
    interpreted = execute(tmp_path, source, False)
    native = execute(tmp_path, source, True)
    assert len(interpreted) == len(expected)
    assert len(native) == len(interpreted)
    for actual, wanted, compiled in zip(interpreted, expected, native):
        try:
            assert abs(float(actual) - float(wanted)) <= 1e-12
            assert abs(float(compiled) - float(actual)) <= 1e-12
        except ValueError:
            assert actual == wanted
            assert compiled == actual


def test_multi_aggregates_after_runtime_record_filter_and_sort(tmp_path):
    assert_parity(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number
let people = [Person("Lin", 27, 9), Person("Ada", 36, 8), Person("Bob", 15, 5), Person("Max", 42, 7)]
selected = people where row.age >= 20
ordered = selected sort by row.age asc
total = ordered sum row.age
counted = ordered count
minimum = ordered min row.score
maximum = ordered max row.age
mean = ordered average row.score
show total
show counted
show minimum
show maximum
show mean
''', ["105", "3", "7", "42", "8"])


def test_multi_aggregates_after_runtime_record_filter_map(tmp_path):
    assert_parity(tmp_path, '''
record Measurement:
    value: Number
    score: Number
    accepted: Boolean
let source = [Measurement(10, 3, true), Measurement(20, 8, false), Measurement(30, 5, true), Measurement(40, 9, true)]
selected = source where row.accepted == true
projected = selected map row.value * 2
total = projected sum item
counted = projected count
minimum = projected min item
maximum = projected max item
mean = projected average item
show total
show counted
show minimum
show maximum
show mean
''', ["160", "3", "20", "80", "53.3333333333333"])




def test_multi_aggregates_after_reassigned_numeric_pipeline(tmp_path):
    assert_parity(tmp_path, '''
let values = [1, 2, 3, 4, 5, 6]
current = values where item >= 4
current = current map item + 1
current = current where item >= 6
current = current map item * 2
total = current sum item
counted = current count
minimum = current min item
maximum = current max item
mean = current average item
show total
show counted
show minimum
show maximum
show mean
''', ["26", "2", "12", "14", "13"])


def test_multi_aggregates_after_reassigned_record_pipeline(tmp_path):
    assert_parity(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number
let people = [Person("Ada", 36, 91), Person("Bob", 15, 88), Person("Lin", 27, 95), Person("Max", 42, 72), Person("Eve", 20, 90)]
selected = people where row.age >= 18
selected = selected where row.score >= 90
selected = selected where row.age < 40
scores = selected map row.score
scores = scores map item + 5
scores = scores where item >= 95
total = scores sum item
counted = scores count
minimum = scores min item
maximum = scores max item
mean = scores average item
show total
show counted
show minimum
show maximum
show mean
''', ["291", "3", "95", "100", "97"])
