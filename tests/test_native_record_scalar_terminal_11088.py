import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "program.sl"
    out = tmp_path / "program"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_record_filter_scalar_sort_reduce(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    age: Number
    score: Number
let people = [Person(20, 90), Person(30, 70), Person(40, 95)]
selected = people where row.age >= 30 and row.score > row.age * 2
mapped = selected map row.score + row.age
ordered = mapped sort by item desc
total = ordered reduce 0 with acc + item
show total
''')
    assert out == ['235']


def test_nested_record_numeric_field_crosses_scalar_boundary(tmp_path):
    out = build_run(tmp_path, '''
record Address:
    city: Text
    code: Number
record Person:
    name: Text
    address: Address
let people = [Person("Ada", Address("London", 41)), Person("Bob", Address("York", 20)), Person("Lin", Address("Paris", 35))]
selected = people where row.address.code >= 30
mapped = selected map row.address.code + 1
ordered = mapped sort by item asc
total = ordered reduce 0 with acc + item
show total
''')
    assert out == ['78']
