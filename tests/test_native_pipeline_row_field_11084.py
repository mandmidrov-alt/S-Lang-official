import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / "program.sl"
    out = tmp_path / "program"
    src.write_text(source)
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()

def test_row_field_survives_filter_to_function_map_and_sort_reduce(tmp_path):
    out = build_run(tmp_path, '''function keep(x: Number) -> Boolean:
    return x >= 2

function double(x: Number) -> Number:
    return x * 2

data numbers:
    a value 3
    b value 1
    c value 4
    d value 2

filtered = numbers where keep(row.value)
scaled = filtered map double(row.value)
sorted = scaled sort by item desc
total = sorted reduce 0 with acc + item
show total
''')
    assert out == ["18"]
