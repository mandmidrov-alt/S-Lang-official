"""Deterministic compiler-core stability corpus for S-Lang 0.99.17.

The suite checks that repeated parsing/planning of representative programs
produces identical semantic artifacts. It is a regression guard for the
pre-1.0 specification boundary, not a performance benchmark.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from slang.core import parse, validate
from slang.goal_ir import lower_goals
from slang.goal_plan import analyze_goals
from slang.semantic_graph import build_semantic_graph
from slang.compiler_pipeline import compile_semantic_pipeline

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class StabilityCase:
    name: str
    source: Path

CASES = (
    StabilityCase("collections", ROOT / "examples/fused_reduce.sl"),
    StabilityCase("stateful", ROOT / "examples/coupled_state_machine.sl"),
    StabilityCase("goal", ROOT / "examples/multi_constraint_goal.sl"),
    StabilityCase("physics", ROOT / "examples/two_body.sl"),
)


def run_case(case: StabilityCase) -> dict[str, object]:
    source = case.source.read_text(encoding="utf-8")
    a = parse(source)
    b = parse(source)
    validate(a)
    validate(b)
    ga, gb = build_semantic_graph(a.ast), build_semantic_graph(b.ast)
    gia, gib = lower_goals(a.ast), lower_goals(b.ast)
    pla, plb = analyze_goals(a.ast), analyze_goals(b.ast)
    pipa, pipb = compile_semantic_pipeline(a.ast), compile_semantic_pipeline(b.ast)
    graph_stable = ga == gb and ga.topological_order() == gb.topological_order()
    goal_stable = gia == gib and pla == plb
    pipeline_stable = pipa == pipb
    return {
        "name": case.name,
        "source": str(case.source.relative_to(ROOT)),
        "graph_stable": graph_stable,
        "goal_stable": goal_stable,
        "pipeline_stable": pipeline_stable,
        "stable": graph_stable and goal_stable and pipeline_stable,
    }


def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
