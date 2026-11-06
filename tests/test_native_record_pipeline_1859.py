import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "program.sl"
    out = tmp_path / "program"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_record_filter_map_sort_reduce(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27), Person("Max", 42)]

adults = people where age >= 18
ages = adults map age
ordered = ages sort by item desc
total = ordered reduce 0 with acc + item
show total
''')
    assert out == ["105"]


def test_record_filter_sort_aggregate(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27), Person("Max", 42)]

adults = people where age >= 18
ages = adults map age
ordered = ages sort by item asc
total = ordered sum item
show total
''')
    assert out == ["105"]
