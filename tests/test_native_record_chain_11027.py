import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'records_chain.sl'
    out = tmp_path / 'records_chain'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()

def test_record_map_preserves_structure_after_filter_and_supports_later_filter(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70), Person("Cara", 40, 95)]
adults = people where row.age >= 18
updated = adults map Person(row.name, row.age + 1, row.score)
selected = updated where row.score > row.age * 2
ages = selected map row.age
show ages
''')
    assert out == ['37', '41']

def test_record_map_keeps_text_and_boolean_fields_after_filter(tmp_path):
    out = build_run(tmp_path, '''
record Item:
    name: Text
    active: Boolean
    score: Number

let items = [Item("A", true, 10), Item("B", false, 20), Item("C", true, 30)]
active = items where row.active == true
updated = active map Item(row.name, row.active, row.score + 5)
selected = updated where row.score >= 35
names = selected map row.name
show names
''')
    assert out == ['C']

def test_record_map_can_create_different_record_type_and_keep_it_through_filter(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70), Person("Cara", 40, 95)]
summaries = people map Summary(row.name, row.score - row.age)
selected = summaries where row.value > 50
values = selected map row.value
show values
''')
    assert out == ['54', '55', '55']


def test_record_map_can_change_field_shape_and_preserve_new_fields(tmp_path):
    out = build_run(tmp_path, '''
record Input:
    name: Text
    age: Number
    score: Number

record Output:
    label: Text
    score2: Number

let rows = [Input("A", 20, 30), Input("B", 30, 50)]
converted = rows map Output(row.name, row.score * 2)
selected = converted where row.score2 >= 60
labels = selected map row.label
show labels
''')
    assert out == ['A', 'B']
