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

def test_filter_uses_multiple_row_fields(tmp_path):
    out=build_run(tmp_path, '''data people:
    Alice age 20 score 90
    Bob age 30 score 70
    Carol age 40 score 95

selected = people where row.age >= 30 and row.score > row.age * 2
show selected
''')
    assert out == ['30', '40']

def test_map_uses_multiple_row_fields_and_conditional(tmp_path):
    out=build_run(tmp_path, '''data people:
    Alice age 20 score 90
    Bob age 30 score 70
    Carol age 40 score 95

mapped = people map if row.score > 90 then row.score - row.age else row.score + row.age
show mapped
''')
    assert out == ['110', '100', '55']
