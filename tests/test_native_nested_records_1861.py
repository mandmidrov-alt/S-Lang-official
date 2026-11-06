import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / 'nested.sl'
    out = tmp_path / 'nested'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run([sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_native_nested_record_field_access(tmp_path):
    out = build_run(tmp_path, '''
record Address:
    city: Text
    code: Number

record Person:
    name: Text
    address: Address

let home = Address("Petropavlovsk", 41)
let person = Person("Ada", home)
show person.name
show person.address.city
show person.address.code
''')
    assert out == ['Ada', 'Petropavlovsk', '41']


def test_native_multiple_record_types_can_be_nested(tmp_path):
    out = build_run(tmp_path, '''
record Coordinates:
    x: Number
    y: Number

record Marker:
    label: Text
    position: Coordinates
    active: Boolean

let marker = Marker("A", Coordinates(10, 20), true)
show marker.position.x + marker.position.y
show marker.active
show marker.label
''')
    assert out == ['30', 'true', 'A']
