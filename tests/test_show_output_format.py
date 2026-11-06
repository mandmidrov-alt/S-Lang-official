from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def test_show_prints_values_without_internal_prefix(tmp_path):
    source = tmp_path / "show_output.sl"
    source.write_text('let version = "1.0"\nshow version\nshow 2 + 3\n', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", str(source)],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["1.0", "5"]
    assert "show =" not in result.stdout
