import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'logic.sl'
    out = tmp_path / 'logic'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()

def test_record_function_uses_helper_function_and_conditional(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

function bonus(score: Number, age: Number) -> Number:
    return score + age * 2

function summarize(person: Person) -> Summary:
    let adjusted = bonus(person.score, person.age)
    return Summary(person.name, if person.age >= 18 then adjusted else person.score)

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70)]
summaries = people map summarize(row)
values = summaries map row.value
show values
''')
    assert out == ['162', '70']

def test_record_function_if_can_use_multiple_fields(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number

record Summary:
    label: Text
    value: Number

function summarize(person: Person) -> Summary:
    if person.score > person.age * 2 and person.age >= 18:
        let value = person.score - person.age
        return Summary(person.name, value)
    else:
        let value = person.score + person.age
        return Summary(person.name, value)

let people = [Person("Ada", 36, 90), Person("Bob", 15, 70), Person("Cara", 40, 95)]
summaries = people map summarize(row)
values = summaries map row.value
show values
''')
    assert out == ['54', '85', '55']
