import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source):
    src = tmp_path / 'program.sl'
    out = tmp_path / 'program'
    src.write_text(source, encoding='utf-8')
    p = subprocess.run(
        [sys.executable, '-m', 'slang.cli', 'build', str(src), '-o', str(out), '--backend', 'native'],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_filter_sort_map_aggregate_preserves_row_fields(tmp_path):
    out = build_run(tmp_path, '''
data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 16 score 72
    Eve age 25 score 90

adults = students where age >= 18
ranked = adults sort by score desc
values = ranked map score * 2
total = values sum item
show total
''')
    assert out == ['552']
