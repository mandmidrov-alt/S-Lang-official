import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_backend_capabilities_reports_full_contract():
    p = subprocess.run([sys.executable, "-m", "slang.cli", "backend-capabilities", "examples/fused_reduce.sl"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert "supported_types =" in p.stdout
    assert "supported_operations =" in p.stdout
    assert "memory_models =" in p.stdout
    assert "fusion_strategies =" in p.stdout
    assert "runtime_features =" in p.stdout
