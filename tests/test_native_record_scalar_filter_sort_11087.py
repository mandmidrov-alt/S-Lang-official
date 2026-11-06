import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'program.sl'; out=tmp_path/'program'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_record_filter_preserves_multiple_fields_into_scalar_sort(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number
let people = [Person("Alice", 20, 90), Person("Bob", 30, 70), Person("Carol", 40, 95)]
selected = people where row.age >= 30 and row.score > row.age * 2
mapped = selected map row.score + row.age
ordered = mapped sort by item asc
show ordered
''')
    assert out == ['100', '135']

def test_record_filter_scalar_function_uses_preserved_fields(tmp_path):
    out=build_run(tmp_path, '''
record Person:
    name: Text
    age: Number
    score: Number
function total(x: Number, y: Number) -> Number:
    return x + y
let people = [Person("Alice", 20, 90), Person("Bob", 30, 70), Person("Carol", 40, 95)]
selected = people where row.age >= 30 and row.score > row.age * 2
mapped = selected map total(row.score, row.age)
ordered = mapped sort by item desc
show ordered
''')
    assert out == ['135', '100']
