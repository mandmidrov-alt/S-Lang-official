"""Real-world cross-language comparison suite.

These cases model small practical programs using files, CSV, JSON, text and
structured data. Results are compared across S-Lang, Python and C++.
Timing is descriptive only and is not a language-quality score.
"""
from __future__ import annotations
import shutil
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "benchmarks" / "real_world"

@dataclass(frozen=True)
class RealWorldCase:
    name: str
    slang: Path
    python: Path
    cpp: Path

CASES = tuple(
    RealWorldCase(name, SUITE / f"{name}.sl", SUITE / f"{name}.py", SUITE / f"{name}.cpp")
    for name in (
        "csv_analysis", "json_processing", "text_processing", "statistics",
        "file_roundtrip", "log_analysis", "config_processing",
    )
)


def _lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("#"))


def _canonical(text: str) -> list[float]:
    import re
    return [float(x) for x in re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text)]


def _run(cmd: list[str]) -> tuple[float, str]:
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    elapsed = time.perf_counter() - start
    if proc.returncode:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return elapsed, proc.stdout.strip()


def _equivalent(a: str, b: str) -> bool:
    left, right = _canonical(a), _canonical(b)
    if len(left) != len(right):
        return False
    return all(abs(x - y) <= max(1e-9, 1e-9 * max(abs(x), abs(y), 1.0)) for x, y in zip(left, right))


def run_case(case: RealWorldCase, cxx: str, iterations: int) -> dict[str, object]:
    slang_runs = [_run([sys.executable, "-m", "slang.cli", "run", str(case.slang)]) for _ in range(iterations)]
    python_runs = [_run([sys.executable, str(case.python)]) for _ in range(iterations)]
    binary = SUITE / f".{case.name}_cpp"
    compiled = subprocess.run([cxx, "-O2", "-std=c++17", str(case.cpp), "-o", str(binary)], cwd=ROOT, text=True, capture_output=True)
    if compiled.returncode:
        raise RuntimeError(f"C++ compile failed for {case.name}: {compiled.stderr}")
    try:
        cpp_runs = [_run([str(binary)]) for _ in range(iterations)]
    finally:
        binary.unlink(missing_ok=True)
    s, p, c = slang_runs[0][1], python_runs[0][1], cpp_runs[0][1]
    return {
        "name": case.name,
        "source_lines": {"S-Lang": _lines(case.slang), "Python": _lines(case.python), "C++": _lines(case.cpp)},
        "correctness": {
            "S-Lang_vs_Python": _equivalent(s, p),
            "S-Lang_vs_C++": _equivalent(s, c),
            "Python_vs_C++": _equivalent(p, c),
            "all_match": _equivalent(s, p) and _equivalent(s, c),
        },
        "median_seconds": {
            "S-Lang_interpreter": statistics.median(x[0] for x in slang_runs),
            "Python": statistics.median(x[0] for x in python_runs),
            "C++": statistics.median(x[0] for x in cpp_runs),
        },
    }


def run_suite(iterations: int = 2) -> dict[str, object]:
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    cxx = shutil.which("clang++") or shutil.which("g++")
    if not cxx:
        raise RuntimeError("No C++ compiler found (clang++ or g++)")
    cases = [run_case(case, cxx, iterations) for case in CASES]
    return {
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "correct": sum(1 for row in cases if row["correctness"]["all_match"]),
            "all_correct": all(row["correctness"]["all_match"] for row in cases),
            "timings_are_informational": True,
            "iterations": iterations,
        },
    }
