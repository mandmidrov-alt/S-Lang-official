import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / "nested_collection.sl"
    out = tmp_path / "nested_collection"
    src.write_text(source, encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_nested_record_collection_filter_and_map(tmp_path):
    out = build_run(tmp_path, '''
record Address:
    city: Text
    code: Number

record Person:
    name: Text
    address: Address

let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20)), Person("Lin", Address("C", 55))]
selected = people where row.address.code >= 40
codes = selected map row.address.code
show codes
''')
    assert out == ["41", "55"]


def test_nested_record_collection_supports_logical_filter(tmp_path):
    out = build_run(tmp_path, '''
record Address:
    city: Text
    code: Number

record Person:
    name: Text
    address: Address

let people = [Person("Ada", Address("A", 41)), Person("Bob", Address("B", 20)), Person("Lin", Address("C", 55))]
selected = people where row.address.code >= 40 and row.address.code < 50
codes = selected map row.address.code
show codes
''')
    assert out == ["41"]
