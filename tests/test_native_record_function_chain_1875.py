import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'record_function_chain.sl'
    out = tmp_path / 'record_function_chain'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()

def test_multiple_record_to_record_maps_preserve_order_and_data(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Bob", 15, false), Person("Lin", 27, true), Person("Ada", 36, true)]
active = people where row.active == true
changed = active map upgrade(row)
changed_again = changed map promote(row)
ages = changed_again map row.age
show ages
''')
    assert out == ['38', '47']

def test_multiple_record_to_record_maps_then_sort_and_aggregate(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Bob", 15, false), Person("Lin", 27, true), Person("Ada", 36, true)]
active = people where row.active == true
changed = active map upgrade(row)
changed_again = changed map promote(row)
ordered = changed_again sort by row.age asc
total = ordered sum row.age
show total
''')
    assert out == ['85']

def test_record_to_record_map_after_sort_then_second_record_map(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 27, true), Person("Bob", 15, false)]
active = people where row.active == true
ordered = active sort by row.age desc
changed = ordered map upgrade(row)
changed_again = changed map promote(row)
ages = changed_again map row.age
show ages
''')
    assert out == ['47', '38']

def test_record_to_record_chain_can_be_filtered_again(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 17, true), Person("Bob", 15, false)]
changed = people map upgrade(row)
changed_again = changed map promote(row)
selected = changed_again where row.age >= 40
ages = selected map row.age
show ages
''')
    assert out == ['47']

def test_post_sort_record_chain_feeds_terminal_aggregate(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 27, true), Person("Bob", 15, false)]
active = people where row.active == true
ordered = active sort by row.age asc
changed = ordered map upgrade(row)
changed_again = changed map promote(row)
total = changed_again sum row.age
show total
''')
    assert out == ['85']

def test_interleaved_record_maps_and_filters_before_sort(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Ada", 20, true), Person("Lin", 27, true), Person("Bob", 15, false), Person("Max", 34, true)]
changed = people map upgrade(row)
selected = changed where row.age >= 28
promoted = selected map promote(row)
selected_again = promoted where row.age < 45
ordered = selected_again sort by row.age asc
ages = ordered map row.age
show ages
''')
    assert out == ['38']


def test_filter_after_sort_is_preserved_across_post_sort_maps(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 27, true), Person("Bob", 15, false)]
active = people where row.active == true
ordered = active sort by row.age asc
changed = ordered map upgrade(row)
selected = changed where row.age >= 30
changed_again = selected map promote(row)
total = changed_again sum row.age
show total
''')
    assert out == ['47']
