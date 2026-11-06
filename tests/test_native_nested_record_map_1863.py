from pathlib import Path
import subprocess, sys
ROOT = Path(__file__).resolve().parents[1]
def build_run(src_text,tmp_path):
    src=tmp_path/'nested.sl'; exe=tmp_path/'nested'; src.write_text(src_text)
    subprocess.run([sys.executable,str(ROOT/'build_native.py'),str(src),'-o',str(exe)],cwd=ROOT,check=True)
    return subprocess.check_output([str(exe)],text=True).strip().splitlines()
def test_native_map_constructs_nested_record_and_projects_field(tmp_path):
    src='''
record Address:
    city: Text
    code: Number
record Person:
    name: Text
    address: Address
let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20))]
updated = people map Person(row.name, Address(row.address.city, row.address.code + 1))
codes = updated map row.address.code
show codes
'''
    assert build_run(src,tmp_path)==['42','21']
def test_native_map_constructs_nested_text_record(tmp_path):
    src='''
record Address:
    city: Text
    code: Number
record Person:
    name: Text
    address: Address
let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20))]
updated = people map Person(row.name, Address(row.address.city, row.address.code + 1))
cities = updated map row.address.city
show cities
'''
    assert build_run(src,tmp_path)==['A','B']
