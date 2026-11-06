import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def build_run(tmp_path, source):
    src=tmp_path/'records_terminal.sl'; out=tmp_path/'records_terminal'; src.write_text(source,encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True); assert r.returncode==0,r.stderr
    return r.stdout.splitlines()
def test_record_sum(tmp_path):
    assert build_run(tmp_path,'''\nrecord Person:\n    name: Text\n    age: Number\n\nlet people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27)]\ntotal = people sum row.age\nshow total\n''')==['78']
def test_record_filter_map_sum(tmp_path):
    assert build_run(tmp_path,'''\nrecord Person:\n    name: Text\n    age: Number\n    active: Boolean\n\nlet people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Lin", 27, true)]\nselected = people where row.active == true\nages = selected map row.age\ntotal = ages sum item\nshow total\n''')==['63']
def test_record_reduce_after_sort(tmp_path):
    assert build_run(tmp_path,'''\nrecord Person:\n    name: Text\n    age: Number\n\nlet people = [Person("Lin", 27), Person("Ada", 36), Person("Bob", 15)]\nordered = people sort by row.age asc\ntotal = ordered reduce 0 with acc + item.age\nshow total\n''')==['78']
def test_record_count_text_field(tmp_path):
    assert build_run(tmp_path,'''\nrecord Person:\n    name: Text\n    age: Number\n\nlet people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 27)]\ntotal = people count row.name\nshow total\n''')==['3']
