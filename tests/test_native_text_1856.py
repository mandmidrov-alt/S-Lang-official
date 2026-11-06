from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run_native(src, tmp_path):
    f=tmp_path/"split.sl"
    f.write_text(src, encoding="utf-8")
    out=tmp_path/"split"
    subprocess.run([sys.executable,"-m","slang.cli","build",str(f),"-o",str(out),"--backend","native"],cwd=ROOT,check=True)
    return subprocess.run([str(out)],cwd=ROOT,text=True,capture_output=True,check=True).stdout

def test_native_text_split(tmp_path):
    out=run_native('let parts = split("alpha,beta,gamma", ",")\nshow parts\n', tmp_path)
    assert out == "alpha\nbeta\ngamma\n"

def test_native_text_split_empty_separator(tmp_path):
    out=run_native('let parts = split("alpha", "")\nshow parts\n', tmp_path)
    assert out == "alpha\n"
