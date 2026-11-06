import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def native_run(tmp_path, source):
    src = tmp_path / 'case.sl'
    out = tmp_path / 'case'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run(
        [sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_native_entity_fields_and_direct_property(tmp_path):
    out = native_run(tmp_path, '''
entity Planet:
    mass: kg
    position: m
    velocity: mps

property Planet.speed -> mps:
    return self.velocity

let earth = Planet(5.972e24 kg, 1.496e11 m, 29780 mps)
show earth.mass, earth.position, earth.speed
''')
    assert out == ['5.972e+24 kg', '149600000000 m', '29780 mps']


def test_native_circle_derived_properties(tmp_path):
    out = native_run(tmp_path, '''
circle disk:
    center 0 m
    radius 10 m

show disk.area, disk.circumference
''')
    assert out == ['314.159265358979 m2', '62.8318530717959 m']
