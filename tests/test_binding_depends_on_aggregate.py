import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_binding_can_use_aggregate_result(tmp_path):
    source = '''let samples = [12, 18, 7, 25, 16, 31, 22]
peak = samples max
let verdict = if peak >= 30 then "high peak detected" else "normal range"
show peak
show verdict
'''
    path = tmp_path / "aggregate_binding.sl"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", str(path)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == [
        "31", "high peak detected"
    ]
