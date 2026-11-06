import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src=tmp_path/'program.sl'; out=tmp_path/'program'
    src.write_text(source)
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out)],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_native_stable_sort_ascending(tmp_path):
    out=build_run(tmp_path, '''data numbers:\n    a value 3\n    b value 1\n    c value 2\n\nsorted = numbers sort by row.value asc\nshow sorted\n''')
    assert out == ['1','2','3']

def test_native_stable_sort_descending_after_filter_and_map(tmp_path):
    out=build_run(tmp_path, '''function double(x: Number) -> Number:\n    return x * 2\n\ndata numbers:\n    a value 3\n    b value 1\n    c value 2\n    d value 2\n\nfiltered = numbers where row.value >= 2\nscaled = filtered map double(row.value)\nsorted = scaled sort by item desc\nshow sorted\n''')
    assert out == ['6','4','4']
