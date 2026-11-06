import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(tmp_path, source):
    src=tmp_path/'text_reduce.sl'; out=tmp_path/'text_reduce'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_text_reduce_after_filter_map_sort(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15), Person("Eve", 20)]
selected = people where row.age >= 20
ordered = selected map row.label
ordered = ordered sort by item asc
joined = ordered reduce "" with acc + item
show joined
''') == ['AdaEveLin']

def test_text_reduce_empty_uses_initial(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("Lin", 27), Person("Ada", 36)]
selected = people where row.label == "Tokyo"
ordered = selected map row.label
ordered = ordered sort by item asc
joined = ordered reduce "prefix:" with acc + item
show joined
''') == ['prefix:']
