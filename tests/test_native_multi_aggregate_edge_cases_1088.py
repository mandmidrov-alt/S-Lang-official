"""Regression coverage for sorted record multi-aggregates and empty inputs."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_source(tmp_path, source, native):
    source_path = tmp_path / ("native.sl" if native else "interpreter.sl")
    source_path.write_text(source, encoding="utf-8")
    if native:
        executable = tmp_path / "native_edge_case"
        build = subprocess.run(
            [sys.executable, "-m", "slang.cli", "build", str(source_path), "-o", str(executable), "--backend", "native"],
            cwd=ROOT, text=True, capture_output=True, timeout=120,
        )
        assert build.returncode == 0, build.stderr
        command = [str(executable)]
    else:
        command = [sys.executable, "-m", "slang.cli", "run", str(source_path)]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)


def test_sorted_record_post_filters_feed_shared_multi_aggregate_scan(tmp_path):
    source = '''
record Person:
    name: Text
    age: Number
    score: Number
    active: Boolean
let people = [Person("Ada", 36, 91, true), Person("Bob", 15, 88, false), Person("Lin", 27, 95, true), Person("Max", 42, 72, true), Person("Eve", 20, 90, true)]
selected = people where row.active == true
ordered = selected sort by row.age asc
postfiltered = ordered where row.score >= 90
postfiltered_again = postfiltered where row.age < 40
total = postfiltered_again sum row.age
counted = postfiltered_again count
minimum = postfiltered_again min row.score
maximum = postfiltered_again max row.age
mean = postfiltered_again average row.score
show total
show counted
show minimum
show maximum
show mean
'''
    expected = ["83", "3", "90", "36", "92"]
    interpreted = run_source(tmp_path, source, False)
    native = run_source(tmp_path, source, True)
    assert interpreted.returncode == 0, interpreted.stderr
    assert native.returncode == 0, native.stderr
    assert interpreted.stdout.splitlines() == expected
    assert native.stdout.splitlines() == expected


def test_single_record_multi_aggregate_matches_interpreter(tmp_path):
    source = '''
record Measurement:
    value: Number
    score: Number
let measurements = [Measurement(12, 7)]
total = measurements sum row.value
counted = measurements count
minimum = measurements min row.score
maximum = measurements max row.value
mean = measurements average row.score
show total
show counted
show minimum
show maximum
show mean
'''
    expected = ["12", "1", "7", "12", "7"]
    interpreted = run_source(tmp_path, source, False)
    native = run_source(tmp_path, source, True)
    assert interpreted.returncode == 0, interpreted.stderr
    assert native.returncode == 0, native.stderr
    assert interpreted.stdout.splitlines() == expected
    assert native.stdout.splitlines() == expected


def test_empty_filtered_record_multi_aggregate_fails_consistently(tmp_path):
    source = '''
record Person:
    name: Text
    age: Number
    score: Number
let people = [Person("Ada", 36, 91), Person("Lin", 27, 95)]
selected = people where row.age > 100
total = selected sum row.age
counted = selected count
minimum = selected min row.score
maximum = selected max row.age
mean = selected average row.score
show total
show counted
show minimum
show maximum
show mean
'''
    interpreted = run_source(tmp_path, source, False)
    native = run_source(tmp_path, source, True)
    assert interpreted.returncode != 0
    assert native.returncode != 0
    assert "empty collection" in (interpreted.stderr + interpreted.stdout)
    assert "empty collection" in (native.stderr + native.stdout)
