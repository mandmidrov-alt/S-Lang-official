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

def test_text_field_filter_and_map(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    active: Boolean

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Lin", 27, true)]
selected = people where row.name != "Bob" and row.active == true
names = selected map row.name
show names
''')
    assert out == ['Ada','Lin']

def test_boolean_field_filter_and_map(tmp_path):
    out=build_run(tmp_path, '''
record Device:
    name: Text
    active: Boolean

let devices = [Device("A", true), Device("B", false), Device("C", true)]
selected = devices where row.active == true
flags = selected map row.active
show flags
''')
    assert out == ['true','true']
