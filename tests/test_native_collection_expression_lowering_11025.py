import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'program.sl'; out=tmp_path/'program'
    src.write_text(source)
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_conditional_and_power_in_map(tmp_path):
    out=build_run(tmp_path, '''data numbers:
    a value 2
    b value 3

mapped = numbers map if row.value > 2 then row.value ^ 2 else row.value + 1
show mapped
''')
    assert out == ['3', '9']

def test_nested_arithmetic_and_logical_predicate(tmp_path):
    out=build_run(tmp_path, '''data numbers:
    a value 2
    b value 3
    c value 5

filtered = numbers where not (row.value + 1 < 3) and (row.value * 2 >= 6)
show filtered
''')
    assert out == ['3', '5']

def test_filter_preserves_multiple_record_fields_for_downstream_map(tmp_path):
    out=build_run(tmp_path, '''data people:
    Alice age 20 score 90
    Bob age 30 score 70
    Carol age 40 score 95

selected = people where row.age >= 30 and row.score > row.age * 2
mapped = selected map if row.score > 90 then row.score - row.age else row.score + row.age
show mapped
''')
    assert out == ['100', '55']

