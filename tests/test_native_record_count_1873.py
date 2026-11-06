import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'records_count.sl'; out=tmp_path/'records_count'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_record_count_without_field(tmp_path):
    assert build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15)]
ordered = people sort by row.age asc
total = ordered count
show total
''') == ['3']

def test_record_count_text_field_after_record_function(tmp_path):
    assert build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1)
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15)]
changed = people map upgrade(row)
ordered = changed sort by row.age asc
total = ordered count row.name
show total
''') == ['3']
