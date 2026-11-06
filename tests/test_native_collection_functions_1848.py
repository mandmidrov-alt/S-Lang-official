import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def test_native_map_can_call_number_function(tmp_path):
    src=tmp_path/'map.sl'; out=tmp_path/'map'
    src.write_text('''function triple(x: Number) -> Number:\n    return x * 3\n\ndata numbers:\n    a value 1\n    b value 2\n    c value 3\nscaled = numbers map triple(row.value)\nshow scaled\n''')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],text=True,capture_output=True); assert r.returncode==0; assert r.stdout.splitlines()==['3','6','9']
def test_native_filter_can_call_boolean_function(tmp_path):
    src=tmp_path/'filter.sl'; out=tmp_path/'filter'
    src.write_text('''function keep(x: Number) -> Boolean:\n    return x >= 2\n\ndata numbers:\n    a value 1\n    b value 2\n    c value 3\nfiltered = numbers where keep(row.value)\nshow filtered\n''')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],text=True,capture_output=True); assert r.returncode==0; assert r.stdout.splitlines()==['2','3']
