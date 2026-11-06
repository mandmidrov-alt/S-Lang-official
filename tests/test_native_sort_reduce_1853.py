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

def test_native_sort_then_reduce(tmp_path):
    out=build_run(tmp_path, '''data numbers:\n    a value 3\n    b value 1\n    c value 4\n    d value 2\n\nsorted = numbers sort by row.value asc\ntotal = sorted reduce 0 with acc + value\nshow total\n''')
    assert out == ['10']

def test_native_sort_then_reduce_product_desc(tmp_path):
    out=build_run(tmp_path, '''data numbers:\n    a value 2\n    b value 4\n    c value 3\n\nsorted = numbers sort by row.value desc\nproduct = sorted reduce 1 with acc * value\nshow product\n''')
    assert out == ['24']
