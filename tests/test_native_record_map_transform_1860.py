import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'records.sl'; out=tmp_path/'records'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_native_map_constructs_same_record_with_transformed_numeric_field(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15)]
updated = people map Person(row.name, row.age + 1)
ages = updated map age
show ages
''')
    assert out == ['37','16']

def test_native_map_constructs_record_with_boolean_and_text_fields(tmp_path):
    out=build_run(tmp_path, '''
record Item:
    name: Text
    active: Boolean
    score: Number

let items = [Item("A", true, 10), Item("B", false, 20)]
updated = items map Item(row.name, row.active, row.score + 5)
scores = updated map score
show scores
''')
    assert out == ['15','25']
