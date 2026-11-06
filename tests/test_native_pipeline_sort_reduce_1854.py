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

def test_filter_map_sort_reduce(tmp_path):
    out=build_run(tmp_path, '''function keep(x: Number) -> Boolean:\n    return x >= 2\n\nfunction double(x: Number) -> Number:\n    return x * 2\n\ndata numbers:\n    a value 3\n    b value 1\n    c value 4\n    d value 2\n\nfiltered = numbers where keep(row.value)\nscaled = filtered map double(row.value)\nsorted = scaled sort by item desc\ntotal = sorted reduce 0 with acc + item\nshow total\n''')
    assert out == ['18']

def test_filter_sort_reduce_without_map(tmp_path):
    out=build_run(tmp_path, '''data numbers:\n    a value 5\n    b value 2\n    c value 4\n    d value 1\n\nfiltered = numbers where row.value >= 2\nsorted = filtered sort by item asc\ntotal = sorted reduce 0 with acc + value\nshow total\n''')
    assert out == ['11']
