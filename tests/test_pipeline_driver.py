import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mlir_driver_status_reports_missing_tools_without_claiming_readiness():
    p = subprocess.run(
        [sys.executable, str(ROOT / 'build_mlir.py'), '--status'],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert 'MLIR pipeline toolchain' in p.stdout
    assert 'ready = no' in p.stdout
    assert 'mlir-opt = missing' in p.stdout
