"""Practical, end-to-end validation corpus for S-Lang.

This suite is descriptive rather than a benchmark score: it records task shape,
source size and the observable result of executing real S-Lang programs.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from slang.core import parse_file, run, validate, show_value, show_expr_value

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class PracticalCase:
    name: str
    domain: str
    source: Path
    expected: tuple[str, ...]

CASES = (
    PracticalCase("data-pipeline", "data processing", ROOT / "examples/practical_data_pipeline.sl", (
        "show = [Clara(age=34, score=96), Gina(age=37, score=94), Elena(age=23, score=91), Denis(age=41, score=88), Hugo(age=29, score=86)]",
        "show = [192, 176, 182, 188, 172]",
        "show = 455",
        "show = 91",
    )),
    PracticalCase("route-planning", "graph planning", ROOT / "examples/practical_routing.sl", (
        "show = path = Home -> B -> C -> D -> Office, cost = 8",
    )),
    PracticalCase("bounded-allocation", "constraint solving", ROOT / "examples/practical_constraints.sl", (
        "show = {'workers': 8, 'machines': 6}",
    )),
    PracticalCase("sequence-processing", "sequence processing", ROOT / "examples/practical_sequence.sl", (
        "show = [2, 7, 17, 37, 77, 157, 317, 637, 1277, 2557, 5117, 10237]",
        "show = [157, 317, 637, 1277, 2557, 5117, 10237]",
        "show = [471, 951, 1911, 3831, 7671, 15351, 30711]",
        "show = 20299",
    )),
    PracticalCase("record-workflow", "structured records", ROOT / "examples/practical_records.sl", (
        "show = [Clara(age=34, score=96), Denis(age=41, score=88)]",
        "show = [96, 88]",
    )),
    PracticalCase("csv-analysis", "external data", ROOT / "examples/practical_csv.sl", (
        "show = 70",
        "show = ['name', 'age', 'role']",
    )),
    PracticalCase("text-processing", "text processing", ROOT / "examples/practical_text.sl", (
        "show = ['alpha', 'beta', 'gamma', 'delta', 'omega']",
        "show = alpha, beta, gamma, delta, omega",
        "show = 5",
    )),
    PracticalCase("generic-workflow", "generic data", ROOT / "examples/practical_generic.sl", (
        "show = 10",
    )),
    PracticalCase("pipeline-generic-records", "generic pipeline", ROOT / "examples/pipeline_generic_records.sl", (
        "show = 10",
    )),
    PracticalCase("pipeline-csv-chain", "CSV pipeline", ROOT / "examples/pipeline_csv_chain.sl", (
        "show = 91.6666666666667",
    )),
    PracticalCase("pipeline-mixed-chain", "composed pipeline", ROOT / "examples/pipeline_mixed_chain.sl", (
        "show = 550",
    )),
    PracticalCase("collection-utilities", "collection utilities", ROOT / "examples/collection_utilities_125.sl", (
        "show = [3, 1, 2, 4, 5]",
        "show = [3, 1, 2]",
        "show = [2, 4, 5]",
    )),
)

INTENT_TOKENS = {
    "where": "filter",
    "map": "map",
    "sum": "aggregate",
    "average": "aggregate",
    "reduce": "reduce",
    "choose": "goal-selection",
    "find path": "goal-path",
    "satisfy": "constraint-goal",
    "sequence": "sequence",
    "sort by": "ordering",
    "join": "text-join",
    "len": "text-length",
    "first": "generic-selection",
    "distinct": "collection-distinct",
    "take": "collection-slice",
    "skip": "collection-slice",
}

def _output(program):
    actual = []
    for expr in (program.show_exprs or []):
        actual.append(f"show = {show_expr_value(program, expr)}")
    if not program.show_exprs:
        for name, field in program.shows:
            value = show_value(program, name, field)
            actual.append(f"{name}{'' if field == '__value__' else '.' + field} = {value}")
    return tuple(actual)

def _source_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("#"))

def _intent_ops(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    found = []
    for token, label in INTENT_TOKENS.items():
        if token in text:
            found.append(label)
    return found

def run_case(case: PracticalCase) -> dict[str, object]:
    program = parse_file(case.source)
    validate(program)
    run(program)
    actual = _output(program)
    return {
        "name": case.name,
        "domain": case.domain,
        "source": str(case.source.relative_to(ROOT)),
        "source_lines": _source_lines(case.source),
        "intent_operations": _intent_ops(case.source),
        "expected": list(case.expected),
        "actual": list(actual),
        "semantic_match": actual == case.expected,
    }

def run_suite() -> list[dict[str, object]]:
    return [run_case(case) for case in CASES]
