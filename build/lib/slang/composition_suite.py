"""End-to-end validation of composed stateful and declarative pipelines."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from slang.core import parse, run, validate, show_expr_value
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class CompositionCase:
    name: str
    domain: str
    source: Path
    expected: tuple[str, ...]
    expected_kinds: tuple[str, ...]

CASES = (
    CompositionCase(
        "state-filter-map-reduce-choose",
        "single stateful pipeline with branching consumers",
        ROOT / "examples/composed_pipeline.sl",
        (
            "show = [1, 2, 4, 8, 16, 32, 64, 128]",
            "show = [8, 16, 32, 64, 128]",
            "show = [64, 256, 1024, 4096, 16384]",
            "show = 21824",
            "show = 16384",
        ),
        ("sequence", "filter", "map", "reduce", "select"),
    ),
    CompositionCase(
        "two-state-merge",
        "two independent state generators with declarative merge",
        ROOT / "examples/composed_two_states.sl",
        (
            "show = [1, 1, 2, 3, 5, 8]",
            "show = [3, 3, 6, 9, 15, 24]",
            "show = [4, 4, 8, 12, 20, 32]",
            "show = 60",
        ),
        ("sequence", "sequence", "map", "map", "map", "reduce"),
    ),
)

def _output(program):
    return tuple(f"show = {show_expr_value(program, expr)}" for expr in (program.show_exprs or []))

def run_case(case: CompositionCase) -> dict[str, object]:
    program = parse(case.source.read_text(encoding="utf-8"))
    validate(program)
    graph = build_semantic_graph(program.ast)
    actual_graph_kinds = tuple(node.kind for node in graph.nodes)
    run(program)
    actual = _output(program)
    return {
        "name": case.name,
        "domain": case.domain,
        "source": str(case.source.relative_to(ROOT)),
        "expected": list(case.expected),
        "actual": list(actual),
        "semantic_match": actual == case.expected,
        "dependency_graph_match": actual_graph_kinds == case.expected_kinds,
        "dependency_order": list(graph.topological_order()),
        "node_count": len(graph.nodes),
    }

def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
