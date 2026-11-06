"""Expanded end-to-end acceptance matrix for representative S-Lang workflows."""
from __future__ import annotations

from .e2e_suite import ROOT, _cli
from time import perf_counter


def _run_example(name: str, *needles: str, native: bool = False) -> dict[str, object]:
    args = ["run", f"examples/{name}"]
    if native:
        args.append("--native")
    started = perf_counter()
    r = _cli(*args)
    elapsed = round(perf_counter() - started, 3)
    output_match = all(x in r.stdout for x in needles)
    passed = r.returncode == 0 and output_match
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "returncode": r.returncode,
        "output_match": output_match,
        "native": native,
        "elapsed_seconds": elapsed,
        # Keep failure evidence in the JSON result so a full-suite-only failure
        # can be diagnosed without rerunning every example interactively.
        "stdout_tail": r.stdout[-1200:],
        "stderr_tail": r.stderr[-1200:],
        "timed_out": r.returncode == 124 or "timed out after 30 seconds" in r.stderr,
    }


def run_suite() -> dict[str, object]:
    cases = []
    scenarios = [
        ("collection_utilities_125.sl", ("[3, 1, 2, 4, 5]", "[3, 1, 2]"), False),
        ("closures.sl", ("10",), False),
        ("generic_collections.sl", ("[Ada(age=36), Bob(age=15)]", "[[1, 2], [3, 4]]"), False),
        ("json_1294.sl", (), False),
        ("datetime_1297.sl", (), False),
        ("fused_reduce.sl", ("18",), True),
        ("practical_text.sl", ("5", "alpha, beta, gamma, delta, omega"), False),
        ("named_records.sl", (), False),
    ]
    for name, needles, native in scenarios:
        cases.append(_run_example(name, *needles, native=native))
        # Stop at the first failing case: later cases cannot make this matrix
        # release-blocking, and early exit preserves the first useful failure.
        if cases[-1]["status"] != "passed":
            break
    passed = sum(c["status"] == "passed" for c in cases)
    return {
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "release_blocking": passed == len(cases),
            "scope": "expanded stdlib/collections/generics/closures/json/datetime/native end-to-end matrix",
        },
    }
