from __future__ import annotations
import os, signal, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SUITE=Path(__file__).resolve().parent
CASES=["pipeline","reduce","sequence","entity","physics"]
COMMAND_TIMEOUT_SECONDS = 30
SMOKE_MODE = "--smoke" in sys.argv[1:]

def lines(path):
    return sum(1 for x in path.read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#"))

def run(cmd):
    """Run one benchmark command with a hard timeout and actionable diagnostics."""
    t = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # Keep benchmark commands in the benchmark runner's process group.
        # The outer pytest harness can then terminate the whole tree reliably.
    )
    try:
        stdout, stderr = proc.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - t
        proc.kill()
        stdout, stderr = proc.communicate()
        raise RuntimeError(
            f"benchmark command timed out after {elapsed:.1f}s "
            f"(limit {COMMAND_TIMEOUT_SECONDS}s): {' '.join(map(str, cmd))}\n"
            f"stdout:\n{(stdout or '')[-2000:]}\nstderr:\n{(stderr or '')[-2000:]}"
        ) from exc
    dt = time.perf_counter() - t
    if proc.returncode:
        raise RuntimeError(
            f"benchmark command failed (exit {proc.returncode}): {' '.join(map(str, cmd))}\n"
            f"stdout:\n{stdout[-2000:]}\nstderr:\n{stderr[-2000:]}"
        )
    return dt, stdout.strip()

if SMOKE_MODE:
    print("control benchmark smoke mode: C++ compilation skipped", flush=True)
print("case | S-Lang lines | Python lines | C++ lines | S-Lang time | Python time | C++ time", flush=True)
print("---|---:|---:|---:|---:|---:|---:", flush=True)
for case in CASES:
    sl = SUITE / f"{case}.sl"
    py = SUITE / f"{case}.py"
    cpp = SUITE / f"{case}.cpp"
    print(f"running benchmark case: {case}", flush=True)
    st, so = run([sys.executable, "-m", "slang.cli", "run", str(sl)])
    pt, po = run([sys.executable, str(py)])
    cxx = None if SMOKE_MODE else (shutil.which("clang++") or shutil.which("g++"))
    ct = None
    if cxx:
        binary = SUITE / f".{case}_bench"
        try:
            subprocess.run(
                [cxx, "-O2", "-std=c++17", str(cpp), "-o", str(binary)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            ct, _ = run([str(binary)])
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"C++ compilation timed out after {COMMAND_TIMEOUT_SECONDS}s for {cpp.name}"
            ) from exc
        finally:
            binary.unlink(missing_ok=True)
    ctime = f"{ct:.6f}s" if ct is not None else "unavailable"
    print(
        f"{case} | {lines(sl)} | {lines(py)} | {lines(cpp)} | "
        f"{st:.6f}s | {pt:.6f}s | {ctime}",
        flush=True,
    )
