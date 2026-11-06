import subprocess
import sys
from pathlib import Path


def test_native_csv_group_count_direct_source_remains_supported(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,role\nA,engineer\nB,designer\nA,designer\nA,engineer\nB,engineer\n", encoding="utf-8")
    source = tmp_path / "group.sl"
    source.write_text(f'''let rows = read_csv("{csv.as_posix()}")
let result = group_count(rows, "team")
show result
''', encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "slang.cli", "run", str(source), "--native"], cwd=Path(__file__).parents[1], text=True, capture_output=True, check=True)
    assert result.stdout.strip() == "[row(key=A, count=3), row(key=B, count=2)]"


def test_native_csv_group_count_does_not_claim_unsupported_pipeline_binding(tmp_path):
    csv = tmp_path / "people.csv"
    csv.write_text("team,role\nA,engineer\nB,designer\n", encoding="utf-8")
    source = tmp_path / "group.sl"
    source.write_text(f'''let rows = read_csv("{csv.as_posix()}")
selected = rows where item.role == "engineer"
let result = group_count(selected, "team")
show result
''', encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "slang.cli", "run", str(source), "--native"], cwd=Path(__file__).parents[1], text=True, capture_output=True)
    assert result.returncode == 0
    assert result.stdout.strip() == "[row(key=A, count=1)]"
