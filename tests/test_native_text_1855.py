from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run_native(src, tmp_path):
    f=tmp_path/'text.sl'
    f.write_text(src, encoding='utf-8')
    out=tmp_path/'text'
    subprocess.run([sys.executable,'-m','slang.cli','build',str(f),'-o',str(out),'--backend','native'],cwd=ROOT,check=True)
    return subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True,check=True).stdout

def test_native_text_transformations(tmp_path):
    out=run_native('''let a = trim("  Hello  ")\nlet b = lower(a)\nlet c = upper(b)\nlet d = replace(c, "HELLO", "S-LANG")\nshow d\n''', tmp_path)
    assert out == 'S-LANG\n'

def test_native_text_predicates(tmp_path):
    out=run_native('''let a = "Hello World"\nshow starts_with(a, "Hello")\nshow ends_with(a, "World")\n''', tmp_path)
    assert out == 'true\ntrue\n'
