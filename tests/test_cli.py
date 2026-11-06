from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "examples" / "two_body.sl"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "slang.cli", *args],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )


def test_check_command():
    assert run_cli("check", str(SRC)).stdout.strip() == "OK"


def test_emit_slang_mlir_has_high_level_op():
    out = run_cli("emit-slang-mlir", str(SRC)).stdout
    assert '"slang.simulate_gravity"' in out
    assert "func.func @main" in out


def test_build_command(tmp_path):
    exe = tmp_path / "earth"
    run_cli("build", str(SRC), "-o", str(exe))
    out = subprocess.check_output([str(exe)], text=True)
    assert "earth.position = 152194895551.048 m" in out
    assert "earth.velocity = 30283.7889471754 mps" in out



def test_lsp_accepts_vscode_languageclient_arguments():
    result = subprocess.run(
        [sys.executable, "-m", "slang.cli", "lsp", "--stdio", "--clientProcessId", "123", "--help"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
