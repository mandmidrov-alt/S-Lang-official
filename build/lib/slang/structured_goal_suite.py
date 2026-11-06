"""Validation of structured goal-directed state transitions."""
from __future__ import annotations
from pathlib import Path
from slang.core import parse, validate, run, show_expr_value
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).resolve().parents[1]

def run_suite():
    source = ROOT / "examples/structured_goal_satisfy.sl"
    p = parse(source.read_text(encoding="utf-8"))
    validate(p)
    graph = build_semantic_graph(p.ast)
    run(p)
    actual = f"show = {show_expr_value(p, p.show_exprs[0])}"
    expected = "show = [UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 0}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 2}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 4}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 6}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 8}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 10}), UserEntity(type_name='Point', name='Point_value', fields={'x': 1, 'y': 10}), UserEntity(type_name='Point', name='Point_value', fields={'x': 2, 'y': 10})]"
    return [{
        "name": "structured-goal-satisfy",
        "source": str(source.relative_to(ROOT)),
        "expected": expected,
        "actual": actual,
        "semantic_match": actual == expected,
        "dependency_graph_match": any(n.kind == "sequence" for n in graph.nodes),
        "structured_state": True,
        "deterministic": True,
    }]
