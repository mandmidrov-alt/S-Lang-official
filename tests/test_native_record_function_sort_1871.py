import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "record_function_sort.sl"
    out = tmp_path / "record_function_sort"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_record_returning_function_executes_before_sort(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Lin", 27, true)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
ages = ordered map row.age
show ages
''')
    assert out == ["28", "37"]


def test_record_returning_function_preserves_sort_association(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

function shift(person: Person) -> Person:
    return Person(person.name, person.age + 10)

let people = [Person("A", 30), Person("B", 10), Person("C", 20)]
changed = people map shift(row)
ordered = changed sort by row.age asc
names = ordered map row.name
show names
''')
    assert out == ["B", "C", "A"]
