"""End-to-end validation of nested and stateful semantic computation.

This suite checks that S-Lang can keep a structured state across sequence steps,
apply a nested transition function with local branching, and still compose the
result with ordinary declarative collection operations.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from slang.core import parse, run, validate, show_expr_value

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class StatefulCase:
    name: str
    domain: str
    source: Path
    expected: tuple[str, ...]

CASES = (
    StatefulCase("nested-fibonacci", "structured recurrence", ROOT / "examples/stateful_fibonacci.sl", (
        "show = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]",
    )),
    StatefulCase("branching-state", "conditional state transition", ROOT / "examples/stateful_branching.sl", (
        "show = [1, 2, 4, 8, 16, 17, 18, 19, 20, 21]",
    )),
)

def _output(program):
    return tuple(f"show = {show_expr_value(program, expr)}" for expr in (program.show_exprs or []))

def run_case(case: StatefulCase) -> dict[str, object]:
    program = parse(case.source.read_text(encoding="utf-8"))
    validate(program)
    run(program)
    actual = _output(program)
    return {
        "name": case.name,
        "domain": case.domain,
        "source": str(case.source.relative_to(ROOT)),
        "expected": list(case.expected),
        "actual": list(actual),
        "semantic_match": actual == case.expected,
    }

def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
