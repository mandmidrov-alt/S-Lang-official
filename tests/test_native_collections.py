import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_filter_map_pipeline_executes(tmp_path):
    src = tmp_path / "pipeline.sl"
    out = tmp_path / "pipeline"
    src.write_text("""data numbers:\n    a value 1\n    b value 2\n    c value 3\n    d value 4\n\nfiltered = numbers where value >= 2\nscaled = filtered map value * 2\nshow scaled\n""")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    run = subprocess.run([str(out)], text=True, capture_output=True)
    assert run.returncode == 0
    assert run.stdout.splitlines() == ["4", "6", "8"]


def test_native_filter_lowers_control_flow(tmp_path):
    src = tmp_path / "filter.sl"
    src.write_text("""data numbers:\n    a value 1\n    b value 2\n    c value 3\nfiltered = numbers where value > 1\nshow filtered\n""")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "emit-llvm", str(src)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert "fcmp ogt double" in p.stdout
    assert "br i1" in p.stdout
    assert "alloca [3 x double]" in p.stdout


def test_native_map_lowers_arithmetic(tmp_path):
    src = tmp_path / "map.sl"
    src.write_text("""data numbers:\n    a value 1\n    b value 2\nscaled = numbers map value * 3\nshow scaled\n""")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "emit-llvm", str(src)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert "fmul double" in p.stdout
    assert "br label %loop1" in p.stdout
