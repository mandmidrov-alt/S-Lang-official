import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_backend_status_is_explicit():
    p = subprocess.run([sys.executable, "-m", "slang.cli", "backend-status", "examples/two_body.sl"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0
    assert "backend.status" in p.stdout
    assert "toolchain_ready =" in p.stdout


def test_mlir_lowering_consumes_semantic_pipeline():
    p = subprocess.run([sys.executable, "-m", "slang.cli", "lower-mlir", "examples/two_body.sl"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0
    assert "backend.lowering" in p.stdout
    assert "backend = mlir-llvm" in p.stdout
    assert "slang.simulate_gravity" in p.stdout


def test_mlir_backend_rejects_unsupported_domain():
    p = subprocess.run([sys.executable, "-m", "slang.cli", "lower-mlir", "examples/data_generic.sl"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode != 0
    assert "MLIR backend" in p.stderr
