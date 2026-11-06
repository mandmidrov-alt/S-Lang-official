from pathlib import Path
import subprocess, sys

ROOT = Path(__file__).resolve().parents[1]

def build_run(tmp_path, source):
    src = tmp_path / 'main.sl'
    src.write_text(source, encoding='utf-8')
    out = tmp_path / 'main'
    r = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return [x.strip() for x in r.stdout.splitlines() if x.strip()]

def test_boolean_count_native(tmp_path):
    assert build_run(tmp_path, '''record Person:\n    name: Text\n    active: Boolean\n\nlet people = [Person("Ada", true), Person("Bob", false), Person("Lin", true)]\nselected = people where row.active == true\nflags = selected map row.active\ntotal = flags count item\nshow total\n''') == ['2']



def test_boolean_any_native(tmp_path):
    src = """record Person:
    name: Text
    active: Boolean

let people = [Person("Ada", true), Person("Bob", false), Person("Lin", true)]
flags = people map row.active
any_result = flags any item
show any_result
"""
    assert build_run(tmp_path, src) == ['true']

def test_boolean_all_native(tmp_path):
    src = """record Person:
    name: Text
    active: Boolean

let people = [Person("Ada", true), Person("Bob", false), Person("Lin", true)]
flags = people map row.active
all_result = flags all item
show all_result
"""
    assert build_run(tmp_path, src) == ['false']

def test_boolean_any_empty_native(tmp_path):
    src = """record Person:
    name: Text
    active: Boolean

let people = [Person("Ada", true)]
selected = people where row.active == false
flags = selected map row.active
any_result = flags any item
show any_result
"""
    assert build_run(tmp_path, src) == ['false']

def test_boolean_all_empty_native(tmp_path):
    src = """record Person:
    name: Text
    active: Boolean

let people = [Person("Ada", true)]
selected = people where row.active == false
flags = selected map row.active
all_result = flags all item
show all_result
"""
    assert build_run(tmp_path, src) == ['true']
