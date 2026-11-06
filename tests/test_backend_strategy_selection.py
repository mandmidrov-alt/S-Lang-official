import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_native_backend_reports_selected_fusion_strategy():
    p = subprocess.run([sys.executable, "-m", "slang.cli", "emit-llvm", "examples/fused_reduce.sl"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith("; selected-strategy = fused-filter-map-reduce")

def test_native_backend_rejects_unimplemented_selected_partial_fusion(tmp_path):
    src = tmp_path / "long.sl"
    src.write_text("""data numbers:
    a value 1
    b value 2
    c value 3
    d value 4
filtered = numbers where value >= 1
mapped1 = filtered map value * 2
mapped2 = mapped1 map item + 1
total = mapped2 reduce 0 with acc + item
""")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "emit-llvm", str(src)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode != 0
    assert "selected strategy" in p.stderr
