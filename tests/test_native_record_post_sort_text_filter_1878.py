import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def run(tmp_path, source):
    src=tmp_path/'text_filter.sl'; out=tmp_path/'text_filter'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_post_sort_text_filter_then_projection(tmp_path):
    out=run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Ada", 20, true), Person("Lin", 28, true)]
ordered = people sort by row.age asc
selected = ordered where row.name == "Ada"
names = selected map row.name
show names
''')
    assert out == ['Ada', 'Ada']

def test_post_sort_text_filter_then_record_map_and_count(tmp_path):
    out=run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Ada", 20, true), Person("Lin", 28, true)]
ordered = people sort by row.age asc
selected = ordered where row.name != "Bob"
changed = selected map upgrade(row)
counted = changed count
show counted
''')
    assert out == ['3']
