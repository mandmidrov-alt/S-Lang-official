import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source, csv):
    src = tmp_path / "csv_aggregate.sl"
    data = tmp_path / "data.csv"
    out = tmp_path / "csv_aggregate"
    data.write_text(csv, encoding="utf-8")
    source = source.replace("data.csv", str(data).replace("\\", "/"))
    src.write_text(source, encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_native_csv_sum_matches_reference(tmp_path):
    assert build_run(tmp_path, '''
let rows = read_csv("data.csv")
adults = rows where to_number(row.age) >= 18
scores = adults map to_number(row.score)
total = scores sum item
show total
''', "age,score\n17,10\n18,20\n30,40\n") == ["60"]


def test_native_csv_count_matches_reference(tmp_path):
    assert build_run(tmp_path, '''
let rows = read_csv("data.csv")
engineers = rows where row.role == "engineer"
total = engineers count
show total
''', "role\nengineer\ndesigner\nengineer\n") == ["2"]
