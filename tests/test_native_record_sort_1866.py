import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / 'records_sort.sl'
    out = tmp_path / 'records_sort'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run(
        [sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_text_record_sort_ascending(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15)]
ordered = people sort by row.name asc
names = ordered map row.name
show names
''')
    assert out == ['Ada', 'Bob', 'Lin']


def test_text_record_sort_descending_after_filter(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

let people = [Person("Lin", 27, true), Person("Ada", 36, true), Person("Bob", 15, false)]
selected = people where row.active == true
ordered = selected sort by row.name desc
names = ordered map row.name
show names
''')
    assert out == ['Lin', 'Ada']


def test_boolean_record_sort(tmp_path):
    out = build_run(tmp_path, '''
record Device:
    name: Text
    active: Boolean

let devices = [Device("A", true), Device("B", false), Device("C", true)]
ordered = devices sort by row.active asc
names = ordered map row.name
show names
''')
    assert out == ['B', 'A', 'C']
