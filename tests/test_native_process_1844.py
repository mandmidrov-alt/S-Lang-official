import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_run_program_direct_args_and_cwd(tmp_path):
    src = tmp_path / "program.sl"
    if sys.platform.startswith("win"):
        source = 'let result = run_program("cmd.exe", ["/C", "echo", "S-Lang-direct"], "")\nshow result\n'
    else:
        source = 'let result = run_program("printf", ["S-Lang-direct"], "")\nshow result\n'
    src.write_text(source, encoding="utf-8")
    out = tmp_path / ("program.exe" if sys.platform.startswith("win") else "program")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=tmp_path, text=True, capture_output=True)
    assert r.returncode == 0
    assert "0" in r.stdout
    assert "S-Lang-direct" in r.stdout


def test_native_run_program_uses_child_working_directory(tmp_path):
    src = tmp_path / "cwd.sl"
    target = tmp_path / "child"
    target.mkdir()
    if sys.platform.startswith("win"):
        source = f'let result = run_program("cmd.exe", ["/C", "cd"], "{str(target).replace(chr(92), "/")}")\nshow result\n'
    else:
        source = f'let result = run_program("pwd", [], "{target}")\nshow result\n'
    src.write_text(source, encoding="utf-8")
    out = tmp_path / ("cwd.exe" if sys.platform.startswith("win") else "cwd")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=tmp_path, text=True, capture_output=True)
    assert r.returncode == 0
    assert "0" in r.stdout
