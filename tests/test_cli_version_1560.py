import subprocess
import sys
from pathlib import Path


def test_cli_version_command_matches_package_metadata():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", "from slang.cli import main; main()", "version"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "1.0"
