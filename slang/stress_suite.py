"""Larger end-to-end stress corpus for S-Lang 0.99.16.

The suite combines existing semantic features into multi-stage programs. It is
an engineering validation corpus, not a benchmark or a ranking of languages.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from slang.core import parse, run, validate, show_expr_value
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class StressCase:
    name: str
    domain: str
    source: Path
    expected_outputs: tuple[str, ...]
    required_kinds: tuple[str, ...]

CASES = (
    StressCase(
        "data-and-selection",
        "data pipeline with declarative selection",
        ROOT / "examples/practical_data_pipeline.sl",
        (),
        ("filter", "map"),
    ),
    StressCase(
        "composed-state-dataflow",
        "state generator with branching consumers",
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
    StressCase(
        "structured-goal",
        "structured state with multiple declarative constraints",
        ROOT / "examples/multi_constraint_goal.sl",
        (),
        ("goal:transition",),
    ),
    StressCase(
        "coupled-state",
        "interdependent structured state and consumers",
        ROOT / "examples/coupled_state_machine.sl",
        (),
        ("sequence",),
    ),
    StressCase(
        "physics",
        "domain-specific numerical simulation",
        ROOT / "examples/two_body.sl",
        (),
        (),
    ),
)


def _outputs(program) -> tuple[str, ...]:
    return tuple(f"show = {show_expr_value(program, expr)}" for expr in (program.show_exprs or []))


def _lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#"))


def run_case(case: StressCase) -> dict[str, object]:
    program = parse(case.source.read_text(encoding="utf-8"))
    validate(program)
    graph = build_semantic_graph(program.ast)
    run(program)
    actual = _outputs(program)
    required_present = all(kind in tuple(n.kind for n in graph.nodes) for kind in case.required_kinds)
    semantic_match = True if not case.expected_outputs else actual == case.expected_outputs
    return {
        "name": case.name,
        "domain": case.domain,
        "source": str(case.source.relative_to(ROOT)),
        "source_lines": _lines(case.source),
        "node_count": len(graph.nodes),
        "expected": list(case.expected_outputs),
        "actual": list(actual),
        "semantic_match": semantic_match,
        "required_kinds_present": required_present,
        "dependency_order": list(graph.topological_order()),
    }


def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
