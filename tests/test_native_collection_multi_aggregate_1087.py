"""Native multi-aggregate execution for ordinary data-table collections."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_collection_multiple_aggregates_share_one_scan(tmp_path):
    source = tmp_path / "multi.sl"
    executable = tmp_path / "multi"
    source.write_text('''data numbers:
    a value 1
    b value 2
    c value 3
    d value 4

filtered = numbers where value >= 2
scaled = filtered map value * 2
total = scaled sum item
counted = scaled count
minimum = scaled min item
maximum = scaled max item
mean = scaled average item
show total
show counted
show minimum
show maximum
show mean
''', encoding="utf-8")
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    build = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(executable), "--backend", "native"], cwd=ROOT, env=env, text=True, capture_output=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(executable)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["18", "3", "4", "8", "6"]


def test_native_collection_multi_aggregate_ir_uses_one_terminal_loop(tmp_path):
    source = tmp_path / "multi_ir.sl"
    source.write_text('''data numbers:
    a value 1
    b value 2
    c value 3

first = numbers sum value
second = numbers count
third = numbers max value
show first
show second
show third
''', encoding="utf-8")
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    emitted = subprocess.run([sys.executable, "-m", "slang.cli", "emit-llvm", str(source)], cwd=ROOT, env=env, text=True, capture_output=True)
    assert emitted.returncode == 0, emitted.stderr
    assert emitted.stdout.count("agg_loop:") == 1
    assert "%aggacc0" in emitted.stdout and "%aggacc1" in emitted.stdout and "%aggacc2" in emitted.stdout


def test_native_collection_multiple_boolean_and_numeric_terminals(tmp_path):
    source = tmp_path / "multi_bool.sl"
    executable = tmp_path / "multi_bool"
    source.write_text('''data numbers:
    a value 0
    b value 2
    c value 4

sum_value = numbers sum value
counted = numbers count
minimum = numbers min value
maximum = numbers max value
mean = numbers average value
has_nonzero = numbers any value
all_nonzero = numbers all value
show sum_value
show counted
show minimum
show maximum
show mean
show has_nonzero
show all_nonzero
''', encoding="utf-8")
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    build = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(executable), "--backend", "native"], cwd=ROOT, env=env, text=True, capture_output=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(executable)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["6", "3", "0", "4", "2", "true", "false"]


def test_native_collection_multiple_aggregates_read_different_fields(tmp_path):
    source = tmp_path / "multi_fields.sl"
    executable = tmp_path / "multi_fields"
    source.write_text('''data measurements:
    first value 10 score 3
    second value 20 score 8
    third value 30 score 5

sum_values = measurements sum value
minimum_score = measurements min score
maximum_value = measurements max value
mean_score = measurements average score
counted = measurements count
show sum_values
show minimum_score
show maximum_value
show mean_score
show counted
''', encoding="utf-8")
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    build = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(executable), "--backend", "native"], cwd=ROOT, env=env, text=True, capture_output=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(executable)], cwd=ROOT, env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["60", "3", "30", "5.333333333333333", "3"]


def test_native_collection_multiple_aggregates_read_different_fields_after_filter(tmp_path):
    source = tmp_path / "multi_fields_filter.sl"
    executable = tmp_path / "multi_fields_filter"
    source.write_text('''data measurements:
    first value 10 score 3
    second value 20 score 8
    third value 30 score 5

selected = measurements where value >= 20
sum_values = selected sum value
minimum_score = selected min score
maximum_value = selected max value
mean_score = selected average score
counted = selected count
show sum_values
show minimum_score
show maximum_value
show mean_score
show counted
''', encoding="utf-8")
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    build = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(source), "-o", str(executable), "--backend", "native"], cwd=ROOT, env=env, text=True, capture_output=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(executable)], cwd=ROOT, env=env, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["50", "5", "30", "6.5", "2"]
