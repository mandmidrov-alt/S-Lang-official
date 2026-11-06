import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "record_scalar_sort.sl"
    out = tmp_path / "record_scalar_sort"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_record_scalar_map_expression_sort(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27)]
ages = people map row.age + 1
ordered = ages sort by item asc
show ordered
''')
    assert out == ["16", "28", "37"]


def test_record_scalar_function_map_sort(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
function bump(x: Number) -> Number:
    return x + 10
let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27)]
ages = people map bump(row.age)
ordered = ages sort by item desc
show ordered
''')
    assert out == ["46", "37", "25"]


def test_record_scalar_map_sort_then_sum(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27)]
ages = people map row.age + 1
ordered = ages sort by item desc
total = ordered sum item
show total
''')
    assert out == ["81"]
