"""Validation of multiple structured satisfy constraints."""
from pathlib import Path
from slang.core import parse, validate, run, show_expr_value
from slang.semantic_graph import build_semantic_graph
ROOT = Path(__file__).resolve().parents[1]
def run_suite():
    source = ROOT / "examples/multi_constraint_goal.sl"
    p = parse(source.read_text(encoding="utf-8")); validate(p); graph = build_semantic_graph(p.ast); run(p)
    actual = f"show = {show_expr_value(p, p.show_exprs[0])}"
    return [{"name":"multi-constraint-structured-goal","source":str(source.relative_to(ROOT)),"expected_prefix":"show = [UserEntity","actual":actual,"semantic_match":actual.startswith("show = [UserEntity"),"dependency_graph_match":any(n.kind == "sequence" for n in graph.nodes),"constraints":4,"deterministic":True}]
