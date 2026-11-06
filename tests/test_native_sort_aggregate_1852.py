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

def test_native_sort_then_sum(tmp_path):
    out=build_run(tmp_path, '''data numbers:
    a value 3
    b value 1
    c value 4
    d value 2

sorted = numbers sort by row.value asc
total = sorted sum row.value
show total
''')
    assert out == ['10']

def test_native_filter_map_sort_then_average(tmp_path):
    out=build_run(tmp_path, '''function double(x: Number) -> Number:
    return x * 2

data numbers:
    a value 3
    b value 1
    c value 4
    d value 2

filtered = numbers where row.value >= 2
scaled = filtered map double(row.value)
sorted = scaled sort by item desc
avg = sorted average item
show avg
''')
    assert out == ['6']

def test_native_function_filter_map_sort_then_sum(tmp_path):
    out=build_run(tmp_path, '''function keep(x: Number) -> Boolean:
    return x >= 2

function double(x: Number) -> Number:
    return x * 2

data numbers:
    a value 3
    b value 1
    c value 4
    d value 2

filtered = numbers where keep(row.value)
scaled = filtered map double(row.value)
ordered = scaled sort by item desc
total = ordered sum item
show total
''')
    assert out == ['18']


def test_native_function_map_sort_by_row_field_then_aggregate(tmp_path):
    out=build_run(tmp_path, '''function upgrade(x: Number) -> Number:
    return x + 10

data numbers:
    a value 3
    b value 1
    c value 4
    d value 2

scaled = numbers map upgrade(row.value)
ordered = scaled sort by item asc
total = ordered sum item
show total
''')
    assert out == ['50']
