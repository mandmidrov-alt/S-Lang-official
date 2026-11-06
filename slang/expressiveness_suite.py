"""Practical expressiveness corpus for S-Lang 0.99.5.

This is a descriptive engineering comparison, not a performance benchmark.
Each case uses a real S-Lang program and a small hand-written imperative
reference size for the same semantic task. The reference counts are included
only to make the abstraction difference inspectable; they are not a quality
score.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from slang.core import parse, run, validate, show_value, show_expr_value

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ExpressivenessCase:
    name: str
    domain: str
    source: Path
    reference_language: str
    reference_lines: int
    supported_features: tuple[str, ...]
    limitation: str


CASES = (
    ExpressivenessCase(
        "data-ranking", "data processing", ROOT / "examples/practical_data_pipeline.sl",
        "Python", 24, ("where", "map", "sum", "average", "sort by"),
        "General external I/O and arbitrary library calls are outside this example.",
    ),
    ExpressivenessCase(
        "route-planning", "graph search", ROOT / "examples/practical_routing.sl",
        "Python", 29, ("find path", "weighted graph"),
        "The current graph model is semantic and intentionally narrower than a general graph library.",
    ),
    ExpressivenessCase(
        "bounded-allocation", "constraint solving", ROOT / "examples/practical_constraints.sl",
        "Python", 27, ("satisfy", "finite constraints"),
        "Constraint domains are currently finite and intentionally restricted.",
    ),
    ExpressivenessCase(
        "sequence-transform", "sequence processing", ROOT / "examples/practical_sequence.sl",
        "Python", 15, ("sequence", "map", "filter", "sum"),
        "The current sequence form does not expose arbitrary generators or asynchronous streams.",
    ),
    ExpressivenessCase(
        "goal-selection", "semantic selection", ROOT / "examples/goal_pipeline.sl",
        "Python", 14, ("where", "choose", "maximizing"),
        "Selection objectives are limited to the goal forms implemented by GoalIR.",
    ),
    ExpressivenessCase(
        "physics-model", "physics", ROOT / "examples/two_body.sl",
        "Python", 31, ("body", "gravity", "simulate"),
        "Physics support is currently limited to the implemented numerical-computing cases rather than a general numerical-computing API.",
    ),
)


def _nonempty_lines(path: Path) -> int:
    return sum(
        1 for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _intent_features(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    tokens = {
        "where": "where", "map": "map", "sum": "aggregate", "average": "aggregate",
        "sort by": "sort", "find path": "find path", "satisfy": "satisfy",
        "choose": "choose", "sequence": "sequence", "gravity": "gravity",
    }
    return sorted({label for token, label in tokens.items() if re.search(r"\b" + re.escape(token) + r"\b", text) or token in text})


def _output(program) -> tuple[str, ...]:
    actual = []
    for expr in (program.show_exprs or []):
        actual.append(f"show = {show_expr_value(program, expr)}")
    if not program.show_exprs:
        for name, field in program.shows:
            value = show_value(program, name, field)
            actual.append(f"{name}{'' if field == '__value__' else '.' + field} = {value}")
    return tuple(actual)


def run_case(case: ExpressivenessCase) -> dict[str, object]:
    program = parse(case.source.read_text(encoding="utf-8"))
    validate(program)
    run(program)
    slang_lines = _nonempty_lines(case.source)
    return {
        "name": case.name,
        "domain": case.domain,
        "source": str(case.source.relative_to(ROOT)),
        "slang_lines": slang_lines,
        "reference_language": case.reference_language,
        "reference_lines": case.reference_lines,
        "line_reduction": case.reference_lines - slang_lines,
        "line_ratio": round(case.reference_lines / slang_lines, 2),
        "intent_features": _intent_features(case.source),
        "supported_features": list(case.supported_features),
        "limitation": case.limitation,
        "semantic_result_available": bool(_output(program)),
    }


def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]


def gap_report() -> list[dict[str, str]]:
    return [
        {"area": "network I/O", "status": "not implemented", "impact": "the standard library covers local file/directory workflows, while general network clients are still outside the current native subset"},
        {"area": "general concurrency", "status": "not implemented", "impact": "parallel execution is compiler-planning infrastructure, not yet a general user-facing concurrency model"},
        {"area": "general-purpose libraries", "status": "limited", "impact": "package resolution/imports exist, but the ecosystem is much smaller than Python's"},
        {"area": "arbitrary algorithms", "status": "partial", "impact": "goal/data constructs cover selected domains; general imperative control is still narrower than Python/C++"},
        {"area": "production tooling", "status": "limited", "impact": "compiler, diagnostics and packaging are substantially implemented, while a mature debugger and broader production tooling remain to be added"},
    ]
