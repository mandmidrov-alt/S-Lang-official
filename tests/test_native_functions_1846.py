import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_and_run(source, tmp_path):
    src = tmp_path / "program.sl"
    src.write_text(source, encoding="utf-8")
    out = tmp_path / "program"
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out)], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    return subprocess.run([str(out)], cwd=tmp_path, text=True, capture_output=True)


def test_native_typed_function_and_if(tmp_path):
    result = build_and_run('''function abs_value(x: Number) -> Number:
    if x >= 0:
        return x
    else:
        return 0 - x

let result = abs_value(0 - 7)
show result
''', tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "7"


def test_native_function_composition_and_boolean_result(tmp_path):
    result = build_and_run('''function positive(x: Number) -> Boolean:
    if x > 0:
        return true
    else:
        return false

function abs_value(x: Number) -> Number:
    if x >= 0:
        return x
    else:
        return 0 - x

let value = abs_value(0 - 4)
let result = positive(value)
show result
''', tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "true"
