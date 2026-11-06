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

def test_native_list_record_filter_map_field(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27)]
adults = people where age >= 18
ages = adults map age
show ages
''')
    assert out == ['36','27']

def test_native_list_record_map_field_without_filter(tmp_path):
    out=build_run(tmp_path, '''
record Product:
    name: Text
    price: Number

let products = [Product("A", 10), Product("B", 25)]
prices = products map price
show prices
''')
    assert out == ['10','25']
