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

def test_native_filter_map_function_then_sum(tmp_path):
    out=build_run(tmp_path, '''function keep(x: Number) -> Boolean:\n    return x >= 2\n\nfunction triple(x: Number) -> Number:\n    return x * 3\n\ndata numbers:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\n\nfiltered = numbers where keep(row.value)\nscaled = filtered map triple(row.value)\ntotal = scaled sum item\nshow total\n''')
    assert out == ['27']

def test_native_map_function_then_average(tmp_path):
    out=build_run(tmp_path, '''function double(x: Number) -> Number:\n    return x * 2\n\ndata numbers:\n    a value 2\n    b value 4\n    c value 6\n\nscaled = numbers map double(row.value)\navg = scaled average item\nshow avg\n''')
    assert out == ['8']
