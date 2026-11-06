import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_run(tmp_path, source, csv):
    src = tmp_path / "csv_aggregate_1570.sl"
    data = tmp_path / "data.csv"
    out = tmp_path / "csv_aggregate_1570"
    data.write_text(csv, encoding="utf-8")
    source = source.replace("data.csv", str(data).replace("\\", "/"))
    src.write_text(source, encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(out), "--backend", "native"], cwd=ROOT, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    r = subprocess.run([str(out)], cwd=ROOT, text=True, capture_output=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def test_native_csv_min_max_keep_negative_values(tmp_path):
    assert build_run(tmp_path, '''
let rows = read_csv("data.csv")
values = rows map to_number(row.value)
minimum = values min item
show minimum
''', "value\n-8\n-3\n-12\n4\n") == ["-12"]


def test_native_csv_max_keeps_negative_values(tmp_path):
    assert build_run(tmp_path, '''
let rows = read_csv("data.csv")
values = rows map to_number(row.value)
maximum = values max item
show maximum
''', "value\n-8\n-3\n-12\n4\n") == ["4"]


def test_native_csv_average_matches_reference(tmp_path):
    assert build_run(tmp_path, '''
let rows = read_csv("data.csv")
values = rows where to_number(row.value) >= 0
positive = values map to_number(row.value)
mean = positive average item
show mean
''', "value\n-10\n2\n4\n9\n") == ["5"]
