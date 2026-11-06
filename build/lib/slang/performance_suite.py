"""Small performance/stability smoke suite for S-Lang.

This is an engineering regression harness, not a language ranking benchmark.
It measures repeated interpreter/native CLI execution, checks deterministic
outputs, and records median wall-clock time for a few representative programs.
"""
from __future__ import annotations

import hashlib
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class PerformanceCase:
    name: str
    source: Path


CASES = (
    PerformanceCase("fused-reduce", ROOT / "examples/fused_reduce.sl"),
    PerformanceCase("two-body-smoke", ROOT / "benchmarks/two_body_smoke.sl"),
    PerformanceCase("filter-sort", ROOT / "benchmarks/data/filter_sort.sl"),
)

_NUMERIC = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


def _normalize_output(text: str) -> str:
    """Normalize presentation differences while retaining computed values."""
    values = _NUMERIC.findall(text)
    return " ".join(values)


def _run(source: Path, native: bool) -> tuple[float, str]:
    cmd = [sys.executable, "-m", "slang.cli", "run", str(source)]
    if native:
        cmd.append("--native")
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    elapsed = time.perf_counter() - started
    if proc.returncode:
        raise RuntimeError(
            f"failed {'native' if native else 'interpreter'} case {source}:\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return elapsed, _normalize_output(proc.stdout)


def run_case(case: PerformanceCase, iterations: int = 3) -> dict[str, object]:
    if iterations < 2:
        raise ValueError("iterations must be >= 2")
    interpreter = [_run(case.source, False) for _ in range(iterations)]
    native = [_run(case.source, True) for _ in range(iterations)]
    interpreter_values = [row[1] for row in interpreter]
    native_values = [row[1] for row in native]
    interpreter_digest = hashlib.sha256(interpreter_values[0].encode()).hexdigest()
    native_digest = hashlib.sha256(native_values[0].encode()).hexdigest()
    return {
        "name": case.name,
        "source": str(case.source.relative_to(ROOT)),
        "iterations": iterations,
        "interpreter_median_seconds": statistics.median(row[0] for row in interpreter),
        "native_median_seconds": statistics.median(row[0] for row in native),
        "interpreter_deterministic": len(set(interpreter_values)) == 1,
        "native_deterministic": len(set(native_values)) == 1,
        "interpreter_native_result_match": interpreter_values[0] == native_values[0],
        "interpreter_digest": interpreter_digest,
        "native_digest": native_digest,
        "stable": (
            len(set(interpreter_values)) == 1
            and len(set(native_values)) == 1
            and interpreter_values[0] == native_values[0]
        ),
    }


def run_suite(iterations: int = 3) -> list[dict[str, object]]:
    return [run_case(case, iterations) for case in CASES]
