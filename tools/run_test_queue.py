#!/usr/bin/env python3
"""Run pytest files one at a time with hard timeouts and captured diagnostics."""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _kill_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # CREATE_NEW_PROCESS_GROUP gives us a process-group boundary; taskkill
        # is not assumed to be installed, so always fall back to kill().
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            process.kill()


def run_one(path: str, timeout: int) -> int:
    command = [sys.executable, "-m", "pytest", "-vv", "-s", "--disable-warnings", path]
    kwargs = {"cwd": ROOT, "stdout": None, "stderr": None}
    # Write to a regular file, not PIPE: a leaked grandchild inheriting stdout
    # must not prevent the runner from returning after the pytest process exits.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8", errors="replace") as log:
        kwargs["stdout"] = log
        kwargs["stderr"] = subprocess.STDOUT
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        started = time.monotonic()
        process = subprocess.Popen(command, **kwargs)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(process)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[FATAL] could not reap pytest process for {path}", flush=True)
                return 125
            log.flush()
            log.seek(0)
            print(f"\n[TIMEOUT] {path}: exceeded {timeout}s", flush=True)
            print(log.read() or "(no captured output)", flush=True)
            return 124
        elapsed = time.monotonic() - started
        log.flush()
        log.seek(0)
        output = log.read()
    print(f"\n[{'PASS' if process.returncode == 0 else 'FAIL'}] {path}: exit={process.returncode}, elapsed={elapsed:.2f}s", flush=True)
    print(output or "(no output)", flush=True)
    return int(process.returncode or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="pytest test files, run in order")
    parser.add_argument("--timeout", type=int, default=60, help="per-file timeout in seconds (default: 60)")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be at least 1 second")
    failures = []
    for path in args.paths:
        result = run_one(path, args.timeout)
        if result:
            failures.append((path, result))
    print(f"\nQueue summary: {len(args.paths) - len(failures)}/{len(args.paths)} passed; {len(failures)} failed or timed out.")
    for path, code in failures:
        print(f"  - {path}: exit {code}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
