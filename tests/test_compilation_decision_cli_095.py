import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compile_decision_cli_reports_selected_backend():
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "compile-decision", "examples/fused_reduce.sl"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    assert "compilation.decision {" in p.stdout
    assert "backend = native-llvm" in p.stdout
    assert "lowering = selected-backend" in p.stdout
