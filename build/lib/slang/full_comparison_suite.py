"""Complete factual comparison of the current S-Lang corpus with Python/C++.

Control and real-world corpora are executed in separate child processes so
native compiler/runtime state cannot affect the second corpus. The report
keeps correctness, source size, and timing separate; it does not assign a
language-quality score.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "benchmarks" / "full_comparison"


def _run_child(command: str) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, "-m", "slang.cli", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if proc.returncode:
        raise RuntimeError(f"{command} failed:\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout)


def run_suite() -> dict[str, object]:
    control = _run_child("comparison-suite")
    real_world = _run_child("real-world-suite")
    rows = control["cases"] + real_world["cases"]
    totals = {k: sum(row["source_lines"][k] for row in rows) for k in ("S-Lang", "Python", "C++")}
    return {
        "corpora": {"control": control, "real_world": real_world},
        "summary": {
            "cases": len(rows),
            "correct": sum(1 for row in rows if row["correctness"]["all_match"]),
            "all_correct": all(row["correctness"]["all_match"] for row in rows),
            "native_cases": len(control["cases"]),
            "native_supported": control["summary"]["native_supported"],
            "native_consistent": control["summary"]["native_consistent"],
            "source_lines_total": totals,
            "timings_are_informational": True,
            "corpora_isolated": True,
        },
    }


def write_report(result: dict[str, object]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = result["corpora"]["control"]["cases"] + result["corpora"]["real_world"]["cases"]
    lines = [
        "# Full S-Lang / Python / C++ comparison",
        "",
        "Descriptive comparison; no overall score or winner is assigned.",
        f"Result: {result['summary']['correct']}/{result['summary']['cases']} tasks produce matching outputs across S-Lang, Python, and C++.",
        "",
        "| Case | S-Lang LOC | Python LOC | C++ LOC | Match | S-Lang interpreter (s) | Python (s) | C++ (s) | Native match |",
        "|---|---:|---:|---:|:---:|---:|---:|---:|:---:|",
    ]
    for row in rows:
        m = row["median_seconds"]
        native = row.get("native", {})
        native_status = "skipped" if native.get("skipped") else ("yes" if native.get("result_match", True) else "no")
        lines.append(
            f"| {row['name']} | {row['source_lines']['S-Lang']} | {row['source_lines']['Python']} | {row['source_lines']['C++']} | "
            f"{'yes' if row['correctness']['all_match'] else 'no'} | {m['S-Lang_interpreter']:.4f} | {m['Python']:.4f} | {m['C++']:.4f} | "
            f"{native_status} |"
        )
    totals = result["summary"]["source_lines_total"]
    lines += [
        "",
        f"Total corpus source lines: S-Lang {totals['S-Lang']}, Python {totals['Python']}, C++ {totals['C++']}.",
        "",
        "Timing note: measurements include process startup. C++ compilation is excluded from runtime; S-Lang native timing includes its current native invocation, so these numbers are not a pure backend benchmark.",
        "",
        "Infrastructure note: the control and real-world corpora run in isolated child processes.",
        "Native execution note: native checks were skipped for this refreshed LOC-focused report; no native-backend conclusion is drawn.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
