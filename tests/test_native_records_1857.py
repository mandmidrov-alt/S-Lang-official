import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "record.sl"
    out = tmp_path / "record"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run(
        [sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_native_named_record_field_projection(tmp_path):
    out = build_run(tmp_path, '''
record Person:
    name: Text
    age: Number

let ada = Person("Ada", 36)
show ada.name
show ada.age
''')
    assert out == ["Ada", "36"]


def test_native_named_record_boolean_and_numeric_expression(tmp_path):
    out = build_run(tmp_path, '''
record Account:
    balance: Number
    active: Boolean

let account = Account(125.5, true)
let updated = account.balance + 24.5
show updated
show account.active
''')
    assert out == ["150", "true"]
