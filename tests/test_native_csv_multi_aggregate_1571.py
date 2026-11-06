import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_csv_multiple_aggregates_single_scan(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("value,role\n-8,engineer\n-3,artist\n-12,engineer\n4,engineer\n", encoding="utf-8")
    src = tmp_path / "main.sl"
    src.write_text(f'''let rows = read_csv("{csv}")
engineers = rows where row.role == "engineer"
values = engineers map to_number(row.value)
total = values sum item
count = values count
minimum = values min item
maximum = values max item
mean = values average item
show total
show count
show minimum
show maximum
show mean
''', encoding="utf-8")
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    build = subprocess.run([sys.executable, "-m", "slang.cli", "build", str(src), "-o", str(tmp_path / "native"), "--backend", "native"], cwd=ROOT, env=env, text=True, capture_output=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(tmp_path / "native")], cwd=ROOT, text=True, capture_output=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout.splitlines() == ["-16", "3", "-12", "4", "-5.33333333333333"]
