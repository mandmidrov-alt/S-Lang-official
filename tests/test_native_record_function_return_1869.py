from pathlib import Path
from slang.core import parse, validate
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'records_fn_return.sl'; out=tmp_path/'records_fn_return'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_native_record_function_returns_record(tmp_path):
    src='''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Bob", 15, false)]
updated = people map upgrade(row)
ages = updated map row.age
show ages
'''
    assert build_run(tmp_path, src) == ['37','16']

def test_record_function_return_is_semantically_typed(tmp_path):
    src='''
record Person:
    name: Text
    age: Number

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1)

let people = [Person("Ada", 36)]
updated = people map upgrade(row)
'''
    p=parse(src,Path.cwd()); validate(p)
    assert str(p._collection_types['updated']) == 'List<Record<Person>>'
