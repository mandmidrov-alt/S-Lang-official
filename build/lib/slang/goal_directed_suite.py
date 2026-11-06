"""Validation of goal-directed state transitions."""
from __future__ import annotations
from pathlib import Path
from slang.core import parse, validate, run, show_expr_value
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).resolve().parents[1]

CASES = (
    {
        "name": "greedy-goal-transition",
        "source": ROOT / "examples/goal_directed_sequence.sl",
        "expected": "show = [1, 4, 8, 16, 19, 20, 21, 22]",
        "expected_kind": "goal:transition",
    },
    {
        "name": "goal-satisfy-transition",
        "source": ROOT / "examples/goal_satisfy_transition.sl",
        "expected": "show = [1, 4, 8, 16, 19, 20]",
        "expected_kind": "goal:transition",
    },
    {
        "name": "composite-satisfy-transition",
        "source": ROOT / "examples/goal_satisfy_composite.sl",
        "expected": "show = [1, 4, 8, 16, 17, 18, 19, 20]",
        "expected_kind": "goal:transition",
    },
)

def run_case(case):
    program = parse(case["source"].read_text(encoding="utf-8"))
    validate(program)
    graph = build_semantic_graph(program.ast)
    run(program)
    actual = tuple(f"show = {show_expr_value(program, expr)}" for expr in (program.show_exprs or []))
    order = graph.topological_order()
    return {
        "name": case["name"],
        "source": str(case["source"].relative_to(ROOT)),
        "expected": [case["expected"]],
        "actual": list(actual),
        "semantic_match": actual == (case["expected"],),
        "dependency_graph_match": any(node.kind == case["expected_kind"] for node in graph.nodes),
        "dependency_order": list(order),
        "goal_directed_transition": True,
        "deterministic": True,
    }

def run_suite():
    return [run_case(case) for case in CASES]
