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

def test_native_function_predicate_logic_then_sum(tmp_path):
    out=build_run(tmp_path, '''function at_least_two(x: Number) -> Boolean:\n    return x >= 2\n\nfunction below_four(x: Number) -> Boolean:\n    return x < 4\n\nfunction double(x: Number) -> Number:\n    return x * 2\n\ndata numbers:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\n\nfiltered = numbers where at_least_two(row.value) and below_four(row.value)\nscaled = filtered map double(row.value)\ntotal = scaled sum item\nshow total\n''')
    assert out == ['10']

def test_native_not_predicate(tmp_path):
    out=build_run(tmp_path, '''function below_three(x: Number) -> Boolean:\n    return x < 3\n\ndata numbers:\n    a value 1\n    b value 2\n    c value 3\n\nfiltered = numbers where not below_three(row.value)\nselected = filtered map row.value\ntotal = selected sum item\nshow total\n''')
    assert out == ['3']
