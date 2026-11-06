import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_run_executes_program(tmp_path):
    src = tmp_path / "program.sl"
    src.write_text("""data numbers:\n    a value 1\n    b value 2\n    c value 3\n\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\nshow scaled\n""")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "run", "--native", str(src)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == ["4", "6"]


def test_doctor_reports_toolchain_state():
    p = subprocess.run([sys.executable, "-m", "slang.cli", "doctor"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert data["native_build_available"] is True
    assert data["status"] == "ready"


def test_build_still_emits_executable(tmp_path):
    src = tmp_path / "reduce.sl"
    out = tmp_path / "reduce"
    src.write_text("""data numbers:\n    a value 1\n    b value 2\n    c value 3\n\ntotal = numbers reduce 0 with acc + value\nshow total\n""")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    q = subprocess.run([str(out)], text=True, capture_output=True)
    assert q.returncode == 0
    assert q.stdout.splitlines() == ["total = 6"]
