import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_native_run_program_with_environment_is_child_only(tmp_path):
    src = tmp_path / "env.sl"
    if sys.platform.startswith("win"):
        source = 'let result = run_program_with_environment("cmd.exe", ["/C", "echo", "%SLANG_ENV_TEST%"], "", ["SLANG_ENV_TEST=child-only"] )\nshow result\n'
    else:
        source = 'let result = run_program_with_environment("printenv", ["SLANG_ENV_TEST"], "", ["SLANG_ENV_TEST=child-only"] )\nshow result\n'
    src.write_text(source, encoding="utf-8")
    out = tmp_path / ("env.exe" if sys.platform.startswith("win") else "env")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=tmp_path, text=True, capture_output=True, env={k:v for k,v in os.environ.items() if k != "SLANG_ENV_TEST"})
    assert r.returncode == 0
    assert "child-only" in r.stdout

def test_reference_run_program_with_environment():
    from slang.stdlib.process import run_program_with_environment
    result = run_program_with_environment(sys.executable, ["-c", "import os; print(os.environ.get('SLANG_ENV_TEST',''))"], "", ["SLANG_ENV_TEST=reference"] )
    assert result[0] == "0"
    assert "reference" in result[1]
