import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(source, tmp_path):
    src = tmp_path / "conditional.sl"
    out = tmp_path / "conditional"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    return subprocess.run([str(out)], cwd=tmp_path, text=True, capture_output=True)


def test_native_conditional_number_in_function(tmp_path):
    result = build_run('''function classify(x: Number) -> Number:\n    return if x > 10 then 100 else 0\n\nshow classify(12)\nshow classify(3)\n''', tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["100", "0"]


def test_native_conditional_boolean_in_function(tmp_path):
    result = build_run('''function positive(x: Number) -> Boolean:\n    return if x > 0 then true else false\n\nshow positive(2)\nshow positive(0 - 2)\n''', tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["true", "false"]


def test_native_conditional_emits_select(tmp_path):
    src = tmp_path / "select.sl"
    src.write_text('''let value = if 5 > 2 then 10 else 20\nshow value\n''', encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "emit-llvm", str(src)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert "select i1" in p.stdout
