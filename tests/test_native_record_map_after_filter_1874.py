import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'records_map_filter.sl'; out=tmp_path/'records_map_filter'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_record_function_map_consumes_filtered_buffer(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Bob", 15, false), Person("Lin", 27, true), Person("Ada", 36, true)]
active = people where row.active == true
changed = active map upgrade(row)
ages = changed map row.age
show ages
''')
    assert out == ['28','37']

def test_record_function_map_after_filter_then_sort(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Bob", 15, false), Person("Lin", 27, true), Person("Ada", 36, true)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age desc
ages = ordered map row.age
show ages
''')
    assert out == ['37','28']
