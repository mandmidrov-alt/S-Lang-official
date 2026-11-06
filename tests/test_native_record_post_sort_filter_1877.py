import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'post_sort_filter.sl'
    out = tmp_path / 'post_sort_filter'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()

def test_post_sort_filter_compacts_records_before_count(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 17, true), Person("Bob", 15, false)]
changed = people map upgrade(row)
ordered = changed sort by row.age asc
selected = ordered where row.age >= 18
changed_again = selected map upgrade(row)
counted = changed_again count
show counted
''')
    assert out == ['2']

def test_post_sort_filter_feeds_record_aggregate(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 27, true), Person("Bob", 15, false), Person("Max", 34, true)]
changed = people map upgrade(row)
ordered = changed sort by row.age asc
selected = ordered where row.age >= 28
changed_again = selected map upgrade(row)
total = changed_again sum row.age
show total
''')
    assert out == ['103']

