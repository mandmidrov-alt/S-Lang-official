from pathlib import Path
from slang.core import parse, validate
import subprocess, sys
ROOT=Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'records_fn.sl'; out=tmp_path/'records_fn'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()


def test_native_record_predicate_function(tmp_path):
    src = '''
record Person:
    name: Text
    age: Number
    active: Boolean

function adult(person: Person) -> Boolean:
    return person.age >= 18 and person.active == true

let people = [Person("Ada", 36, true), Person("Bob", 15, true), Person("Lin", 27, false), Person("Max", 22, true)]
adults = people where adult(row)
ages = adults map row.age
show ages
'''
    path = tmp_path / 'main.sl'
    path.write_text(src)
    out = build_run(tmp_path, src)
    assert out == ['36', '22']


def test_record_function_is_semantically_typed(tmp_path):
    src='''
record Person:
    name: Text
    age: Number

function adult(person: Person) -> Boolean:
    return person.age >= 18

let people = [Person("Ada", 36), Person("Bob", 15)]
adults = people where adult(row)
'''
    p=parse(src,Path.cwd()); validate(p)
    assert str(p._collection_types['adults']) == 'List<Record<Person>>'
