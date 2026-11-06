#!/usr/bin/env python3
"""Smoke-test the frozen executable's bundled native CSV runtime ABI."""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True, type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    if not executable.is_file():
        raise SystemExit(f"Frozen executable does not exist: {executable}")

    with tempfile.TemporaryDirectory(prefix="slang-frozen-runtime-") as tmp:
        root = Path(tmp)
        csv = root / "people.csv"
        source = root / "csv_sort.sl"
        csv.write_text("team,score\nB,20\nA,30\nA,10\n", encoding="utf-8")
        source.write_text(
            f'let rows = read_csv("{csv.as_posix()}")\n'
            'sorted = rows |> sort by row.score asc\n'
            'show sorted\n',
            encoding="utf-8",
        )
        env = os.environ.copy()
        # The one-file executable must not rely on a compiler installed at runtime.
        env["PATH"] = "" if os.name != "nt" else ""
        completed = subprocess.run(
            [str(executable), "run", "--native-jit", str(source)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=90,
        )
        if completed.returncode != 0:
            raise SystemExit(
                "Frozen native-runtime CSV smoke test failed.\n"
                f"Exit code: {completed.returncode}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )
        output = completed.stdout.strip()
        expected_order = ["score=10", "score=20", "score=30"]
        positions = [output.find(item) for item in expected_order]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            raise SystemExit(
                "Frozen native-runtime CSV smoke test produced unexpected output.\n"
                f"Expected ascending score order {expected_order}; got:\n{output}"
            )
        print("Frozen native-runtime CSV smoke test passed")
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
