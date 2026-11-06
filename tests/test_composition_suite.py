from pathlib import Path
from slang.composition_suite import run_suite
from slang.core import parse_file, validate, run
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).parents[1]

def test_composition_suite_passes():
    results = run_suite()
    assert len(results) == 2
    assert all(row["semantic_match"] for row in results)
    assert all(row["dependency_graph_match"] for row in results)

def test_composed_pipeline_graph_has_branching_dependencies():
    p = parse_file(ROOT / "examples" / "composed_pipeline.sl")
    validate(p)
    graph = build_semantic_graph(p.ast)
    by = graph.by_result()
    assert by["filtered"].dependencies == ("values#1",)
    assert by["squared"].dependencies == ("filtered#1",)
    assert by["total"].dependencies == ("squared#1",)
    assert by["best"].dependencies == ("squared#1",)
    assert graph.topological_order() == (
        "values#1", "filtered#1", "squared#1", "best#1", "total#1"
    )

def test_two_state_pipeline_composes_independent_generators():
    p = parse_file(ROOT / "examples" / "composed_two_states.sl")
    validate(p); run(p)
    assert p._collections["left_values"] == [1, 1, 2, 3, 5, 8]
    assert p._collections["right_values"] == [3, 3, 6, 9, 15, 24]
    assert p._collections["merged"] == [4, 4, 8, 12, 20, 32]
    assert p._collections["sum_right"] == 60
