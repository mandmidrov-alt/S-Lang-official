"""Deterministic end-to-end validation corpus for S-Lang.

The suite checks representative language domains by compiling/parsing and running
real S-Lang programs, then comparing their observable output with fixed semantic
expectations. It intentionally does not score style or performance.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from slang.core import parse, run, validate, show_value, show_expr_value

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ValidationCase:
    name: str
    source: Path
    expected: tuple[str, ...]


CASES = (
    ValidationCase("data-generic", ROOT / "examples/data_generic.sl", (
        "show = [Alice(age=22, score=91), Eve(age=25, score=90), Carol(age=31, score=95)]",
    )),
    ValidationCase("reduce", ROOT / "examples/reduce.sl", (
        "show = 24",
        "show = 10",
    )),
    ValidationCase("goals", ROOT / "examples/goals.sl", (
        "show = {'name': 'Carol', 'age': 31, 'score': 95}",
        "show = {'name': 'Alice', 'age': 22, 'score': 91}",
    )),
    ValidationCase("graph-goal", ROOT / "examples/graph_goals.sl", (
        "show = path = A -> B -> D, cost = 4",
    )),
    ValidationCase("satisfy", ROOT / "examples/satisfy.sl", (
        "show = {'x': 2, 'y': 10}",
    )),
    ValidationCase("state", ROOT / "examples/state.sl", (
        "show = 3",
    )),
    ValidationCase("sequence", ROOT / "examples/sequence.sl", (
        "show = [1, 4, 13, 40, 121, 364, 1093, 3280, 9841, 29524]",
        "show = [2, 8, 26, 80, 242, 728, 2186, 6560, 19682, 59048]",
    )),
    ValidationCase("physics", ROOT / "examples/two_body.sl", (
        "show = 152194895551.048 m",
        "show = 30283.7889471754 mps",
    )),
)


def nonempty_lines(path: Path) -> int:
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def run_case(case: ValidationCase) -> dict[str, object]:
    program = parse(case.source.read_text(encoding="utf-8"))
    validate(program)
    run(program)
    actual = []
    for expr in (program.show_exprs or []):
        actual.append(f"show = {show_expr_value(program, expr)}")
    if not program.show_exprs:
        for name, field in program.shows:
            value = show_value(program, name, field)
            actual.append(f"{name}{'' if field == '__value__' else '.' + field} = {value}")
    actual_tuple = tuple(actual)
    return {
        "name": case.name,
        "source": str(case.source.relative_to(ROOT)),
        "source_lines": nonempty_lines(case.source),
        "expected": list(case.expected),
        "actual": list(actual_tuple),
        "semantic_match": actual_tuple == case.expected,
    }


def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
