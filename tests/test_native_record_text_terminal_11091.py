import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(tmp_path, source):
    src=tmp_path/'text_terminal.sl'; out=tmp_path/'text_terminal'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_text_scalar_sort_then_count(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15), Person("Ada", 20)]
selected = people where row.age >= 20
ordered = selected map row.label
ordered = ordered sort by item asc
total = ordered count
show total
''') == ['3']

def test_text_scalar_sort_then_count_empty(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36)]
selected = people where row.label == "Tokyo"
ordered = selected map row.label
ordered = ordered sort by item asc
total = ordered count
show total
''') == ['0']

def test_text_scalar_sort_then_min(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15)]
selected = people where row.age >= 20
ordered = selected map row.label
ordered = ordered sort by item asc
smallest = ordered min item
show smallest
''') == ['Ada']


def test_text_scalar_sort_then_max_desc(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15)]
selected = people where row.age >= 20
ordered = selected map row.label
ordered = ordered sort by item desc
largest = ordered max item
show largest
''') == ['Lin']
