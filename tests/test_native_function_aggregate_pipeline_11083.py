import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "program.sl"
    out = tmp_path / "program"
    src.write_text(source, encoding="utf-8")
    build = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    return run.stdout.splitlines()


def test_function_filter_map_sum_keeps_row_field_context(tmp_path):
    assert build_run(tmp_path, '''
function keep(x: Number) -> Boolean:
    return x >= 2

function triple(x: Number) -> Number:
    return x * 3

data numbers:
    a value 1
    b value 2
    c value 3
    d value 4

filtered = numbers where keep(row.value)
scaled = filtered map triple(row.value)
total = scaled sum item
show total
''') == ["27"]


def test_function_map_average_uses_fused_numeric_call_lowering(tmp_path):
    assert build_run(tmp_path, '''
function double(x: Number) -> Number:
    return x * 2

data numbers:
    a value 2
    b value 4
    c value 6

scaled = numbers map double(row.value)
avg = scaled average item
show avg
''') == ["8"]
