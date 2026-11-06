"""Cross-language comparison suite for S-Lang, Python, and C++.

This suite compares the same deterministic tasks across the three languages.
It reports source size, correctness, and wall-clock time. Timings are
informational and environment-dependent; they are not a quality score.
"""
from __future__ import annotations

import re
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class ComparisonCase:
    name: str
    slang: Path
    python: Path
    cpp: Path
    kind: str = "numeric"


CASES = (
    ComparisonCase("pipeline", ROOT / "benchmarks/control_suite/pipeline.sl", ROOT / "benchmarks/control_suite/pipeline.py", ROOT / "benchmarks/control_suite/pipeline.cpp"),
    ComparisonCase("reduce", ROOT / "benchmarks/control_suite/reduce.sl", ROOT / "benchmarks/control_suite/reduce.py", ROOT / "benchmarks/control_suite/reduce.cpp"),
    ComparisonCase("sequence", ROOT / "benchmarks/control_suite/sequence.sl", ROOT / "benchmarks/control_suite/sequence.py", ROOT / "benchmarks/control_suite/sequence.cpp"),
    ComparisonCase("entity", ROOT / "benchmarks/control_suite/entity.sl", ROOT / "benchmarks/control_suite/entity.py", ROOT / "benchmarks/control_suite/entity.cpp"),
    ComparisonCase("physics", ROOT / "benchmarks/control_suite/physics.sl", ROOT / "benchmarks/control_suite/physics.py", ROOT / "benchmarks/control_suite/physics.cpp"),
    ComparisonCase("filter-sort", ROOT / "benchmarks/data/filter_sort.sl", ROOT / "benchmarks/data/filter_sort.py", ROOT / "benchmarks/data/filter_sort.cpp"),
    ComparisonCase("circle", ROOT / "benchmarks/geometry/circle.sl", ROOT / "benchmarks/geometry/circle.py", ROOT / "benchmarks/geometry/circle.cpp"),
)

_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_NAMES = re.compile(r"\b[A-Z][A-Za-z0-9_]*\b")


def _lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#"))


def _run(cmd: list[str]) -> tuple[float, str]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    elapsed = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return elapsed, proc.stdout.strip()


def _canonical(text: str, kind: str) -> list[object]:
    text = text.replace("show =", "")
    if kind == "records":
        return _NAMES.findall(text)
    return [float(x) for x in _NUMBER.findall(text)]


def _equivalent(a: str, b: str, kind: str) -> bool:
    left = _canonical(a, kind)
    right = _canonical(b, kind)
    if kind == "records":
        return left == right
    if len(left) != len(right):
        return False
    for x, y in zip(left, right):
        tolerance = max(1e-9, 1e-9 * max(abs(float(x)), abs(float(y)), 1.0))
        if abs(float(x) - float(y)) > tolerance:
            return False
    return True


def _native(case: ComparisonCase) -> tuple[bool, float | None, str]:
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "slang.cli", "run", "--native", str(case.slang)],
        cwd=ROOT, text=True, capture_output=True,
    )
    elapsed = time.perf_counter() - started
    if proc.returncode:
        return False, elapsed, (proc.stderr or proc.stdout).strip().splitlines()[-1] if (proc.stderr or proc.stdout).strip() else "native execution failed"
    return True, elapsed, proc.stdout.strip()


def run_case(case: ComparisonCase, cxx: str, iterations: int = 3, native: bool = True) -> dict[str, object]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    slang_runs = [_run([sys.executable, "-m", "slang.cli", "run", str(case.slang)]) for _ in range(iterations)]
    python_runs = [_run([sys.executable, str(case.python)]) for _ in range(iterations)]
    binary = ROOT / "benchmarks" / "comparison_suite" / f".{case.name.replace('-', '_')}_cpp"
    compile_proc = subprocess.run([cxx, "-O2", "-std=c++17", str(case.cpp), "-o", str(binary)], cwd=ROOT, text=True, capture_output=True)
    if compile_proc.returncode:
        raise RuntimeError(f"C++ compile failed for {case.name}: {compile_proc.stderr}")
    try:
        cpp_runs = [_run([str(binary)]) for _ in range(iterations)]
    finally:
        binary.unlink(missing_ok=True)

    s_out, p_out, c_out = slang_runs[0][1], python_runs[0][1], cpp_runs[0][1]
    if native:
        native_ok, native_time, native_out = _native(case)
        native_result = {"available": native_ok, "seconds": native_time, "result_match": native_ok and _equivalent(s_out, native_out, case.kind), "output": native_out if not native_ok else None}
    else:
        native_result = {"available": False, "skipped": True, "reason": "Native execution was explicitly skipped."}
    return {
        "name": case.name,
        "source_lines": {"S-Lang": _lines(case.slang), "Python": _lines(case.python), "C++": _lines(case.cpp)},
        "correctness": {
            "S-Lang_vs_Python": _equivalent(s_out, p_out, case.kind),
            "S-Lang_vs_C++": _equivalent(s_out, c_out, case.kind),
            "Python_vs_C++": _equivalent(p_out, c_out, case.kind),
            "all_match": _equivalent(s_out, p_out, case.kind) and _equivalent(s_out, c_out, case.kind),
        },
        "median_seconds": {
            "S-Lang_interpreter": statistics.median(x[0] for x in slang_runs),
            "Python": statistics.median(x[0] for x in python_runs),
            "C++": statistics.median(x[0] for x in cpp_runs),
        },
        "native": native_result,
    }


def run_suite(iterations: int = 3, native: bool = True) -> dict[str, object]:
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        raise RuntimeError("No C++ compiler found (clang++ or g++)")
    cases = [run_case(case, cxx, iterations, native=native) for case in CASES]
    return {
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "correct": sum(1 for row in cases if row["correctness"]["all_match"]),
            "all_correct": all(row["correctness"]["all_match"] for row in cases),
            "native_supported": sum(1 for row in cases if row["native"]["available"]),
            "native_consistent": all(not row["native"]["available"] or row["native"].get("result_match", False) for row in cases),
            "native_skipped": not native,
            "timings_are_informational": True,
            "iterations": iterations,
        },
    }
