import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_reduce_llvm_emits_runtime_abi():
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "emit-llvm", "examples/reduce.sl"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0
    assert "@slang_reduce_f64" in p.stdout
    assert "i32 2" in p.stdout
    assert "i32 0" in p.stdout


def test_reduce_native_build_executes(tmp_path):
    out = tmp_path / "reduce"
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", "examples/reduce.sl", "-o", str(out)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    run = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0
    assert "product = 24" in run.stdout
    assert "total = 10" in run.stdout


def test_reduce_native_backend_rejects_nontrivial_recurrence(tmp_path):
    src = tmp_path / "bad.sl"
    src.write_text(
        "data numbers:\n"
        "    a value 1\n"
        "    b value 2\n"
        "total = numbers reduce 0 with acc + value * 2\n"
        "show total\n",
        encoding="utf-8",
    )
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "emit-llvm", str(src)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode != 0
    assert "native reduce supports only" in p.stderr
