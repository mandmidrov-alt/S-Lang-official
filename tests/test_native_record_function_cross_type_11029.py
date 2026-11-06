import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'cross_type.sl'
    out = tmp_path / 'cross_type'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()

def test_record_function_can_return_different_record_type_and_continue_pipeline(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

function summarize(person: Person) -> Summary:
    return Summary(person.name, person.score - person.age)

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70), Person("Cara", 40, 95)]
summaries = people map summarize(row)
selected = summaries where row.value >= 54
values = selected map row.value
show values
''')
    assert out == ['54', '55', '55']

def test_record_function_can_change_schema_twice(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

record Final:
    title: Text
    amount: Number

function summarize(person: Person) -> Summary:
    return Summary(person.name, person.score - person.age)

function finalize(summary: Summary) -> Final:
    return Final(summary.label, summary.value * 2)

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
summaries = people map summarize(row)
finals = summaries map finalize(row)
amounts = finals map row.amount
show amounts
''')
    assert out == ['108', '110']
