from pathlib import Path
from slang.coupled_state_suite import run_suite
from slang.core import parse_file, validate, run
from slang.semantic_graph import build_semantic_graph

ROOT = Path(__file__).parents[1]

def test_coupled_state_suite_passes():
    results = run_suite()
    assert len(results) == 1
    assert all(row["semantic_match"] for row in results)
    assert all(row["dependency_graph_match"] for row in results)

def test_coupled_state_is_atomic_and_graph_is_deterministic():
    p = parse_file(ROOT / "examples" / "coupled_state_machine.sl")
    validate(p); run(p)
    assert p._collections["xs"] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 16, 15, 14, 13]
    assert p._collections["scores"] == [3, 5, 8, 12, 17, 23, 30, 38, 47, 57, 68, 80, 93, 107, 122, 138, 138, 139, 140, 141]
    assert p._collections["large"] == [12, 17, 23, 30, 38, 47, 57, 68, 80, 93, 107, 122, 138, 138, 139, 140, 141]
    assert p._collections["total"] == 1390
    graph = build_semantic_graph(p.ast)
    by = graph.by_result()
    assert by["xs"].dependencies == ("states#1",)
    assert by["scores"].dependencies == ("states#1",)
    assert by["large"].dependencies == ("scores#1",)
    assert by["total"].dependencies == ("large#1",)
    assert set(graph.topological_order()) == {"states#1", "xs#1", "scores#1", "large#1", "total#1"}
