import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(source, tmp_path):
    path = tmp_path / "case.sl"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()


def test_scalar_aggregate_can_omit_item(tmp_path):
    assert run(
        """let values = [2, 4, 6]

total = values sum
avg = values average
low = values min
high = values max
count = values count
show total, avg, low, high, count
""",
        tmp_path,
    ) == ["12", "4", "2", "6", "3"]


def test_record_count_can_omit_item(tmp_path):
    assert run(
        """record Person:
    name: Text
    age: Number

let people = [Person("A", 20), Person("B", 30), Person("C", 40)]
count = people count
show count
""",
        tmp_path,
    ) == ["3"]
