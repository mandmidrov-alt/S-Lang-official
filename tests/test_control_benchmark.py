from pathlib import Path
import os
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "benchmarks" / "control_suite" / "run_benchmark.py"


def test_control_benchmark_runs():
    command = [sys.executable, str(RUNNER), "--smoke"]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=(os.name != "nt"),
    )
    try:
        out, _ = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        out, _ = process.communicate()
        raise AssertionError(f"control benchmark smoke test timed out after 60 seconds:\n{out[-4000:]}")
    assert process.returncode == 0, out[-4000:]
    assert "pipeline |" in out
    assert "sequence |" in out
    assert "physics |" in out
