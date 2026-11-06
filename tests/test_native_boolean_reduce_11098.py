import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(tmp_path, source):
    src=tmp_path/'boolean_reduce.sl'; out=tmp_path/'boolean_reduce'
    src.write_text(source, encoding='utf-8')
    p=subprocess.run([sys.executable,'-m','slang.cli','build',str(src),'-o',str(out),'--backend','native'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stderr
    r=subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    return r.stdout.splitlines()

def test_boolean_reduce_or(tmp_path):
    assert run(tmp_path, '''record Flag:
    active: Boolean
let flags = [Flag(false), Flag(false), Flag(true)]
result = flags reduce false with acc or item.active
show result
''') == ['true']

def test_boolean_reduce_and(tmp_path):
    assert run(tmp_path, '''record Flag:
    active: Boolean
let flags = [Flag(true), Flag(true), Flag(false)]
result = flags reduce true with acc and item.active
show result
''') == ['false']

def test_boolean_reduce_empty_identity(tmp_path):
    assert run(tmp_path, '''record Flag:
    active: Boolean
let flags = [Flag(false), Flag(true)]
selected = flags where row.active == false
result = selected reduce true with acc and item.active
show result
''') == ['false']
