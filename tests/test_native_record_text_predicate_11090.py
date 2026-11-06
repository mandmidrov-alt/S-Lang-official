import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(tmp_path, source):
    src=tmp_path/'text_pred.sl'; out=tmp_path/'text_pred'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_text_equality_predicate_before_scalar_sort(tmp_path):
    assert run(tmp_path, '''
record Person:
    label: Text
    age: Number
let people = [Person("London", 40), Person("Paris", 20), Person("London", 15), Person("Berlin", 30)]
selected = people where row.label == "London"
ordered = selected map row.label
ordered = ordered sort by item asc
show ordered
''') == ['London','London']

def test_text_lexical_predicate_with_numeric_and_logic(tmp_path):
    assert run(tmp_path, '''
record Person:
    city: Text
    age: Number
let people = [Person("London", 40), Person("Paris", 20), Person("Rome", 30), Person("Berlin", 50)]
selected = people where row.city >= "London" and row.age >= 30
ordered = selected map row.city
ordered = ordered sort by item desc
show ordered
''') == ['Rome','London']

def test_text_inequality_predicate_before_scalar_sort(tmp_path):
    assert run(tmp_path, '''
record Person:
    city: Text
let people = [Person("London"), Person("Paris"), Person("London"), Person("Berlin")]
selected = people where row.city != "London"
ordered = selected map row.city
ordered = ordered sort by item asc
show ordered
''') == ['Berlin','Paris']

def test_text_predicate_empty_result_is_safe(tmp_path):
    assert run(tmp_path, '''
record Person:
    city: Text
let people = [Person("London"), Person("Paris")]
selected = people where row.city == "Tokyo"
ordered = selected map row.city
ordered = ordered sort by item asc
show ordered
''') == []
