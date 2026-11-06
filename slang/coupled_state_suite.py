"""End-to-end validation of coupled structured state machines.

The suite intentionally keeps several interdependent values inside one explicit
structured state. This is the current S-Lang model for state that must evolve
atomically: no implicit shared mutable variables are introduced.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from slang.core import parse, run, validate, show_expr_value
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class CoupledStateCase:
    name: str
    source: Path
    expected: tuple[str, ...]
    expected_kinds: tuple[str, ...]

CASES = (
    CoupledStateCase(
        "atomic-coupled-state",
        ROOT / "examples/coupled_state_machine.sl",
        (
            "show = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 16, 15, 14, 13]",
            "show = [3, 5, 8, 12, 17, 23, 30, 38, 47, 57, 68, 80, 93, 107, 122, 138, 138, 139, 140, 141]",
            "show = [12, 17, 23, 30, 38, 47, 57, 68, 80, 93, 107, 122, 138, 138, 139, 140, 141]",
            "show = 1390",
        ),
        ("sequence", "map", "map", "filter", "reduce"),
    ),
)

def _output(program):
    return tuple(f"show = {show_expr_value(program, expr)}" for expr in (program.show_exprs or []))

def run_case(case: CoupledStateCase) -> dict[str, object]:
    program = parse(case.source.read_text(encoding="utf-8"))
    validate(program)
    graph = build_semantic_graph(program.ast)
    run(program)
    actual = _output(program)
    kinds = tuple(node.kind for node in graph.nodes)
    return {
        "name": case.name,
        "source": str(case.source.relative_to(ROOT)),
        "expected": list(case.expected),
        "actual": list(actual),
        "semantic_match": actual == case.expected,
        "dependency_graph_match": kinds == case.expected_kinds,
        "dependency_order": list(graph.topological_order()),
        "atomic_state_model": True,
    }

def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
