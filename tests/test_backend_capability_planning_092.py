from pathlib import Path

from slang.backend import native_capabilities
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.core import parse

ROOT = Path(__file__).resolve().parents[1]

def test_execution_plan_can_be_constrained_by_backend_capabilities():
    ast = parse((ROOT / "examples/fused_reduce.sl").read_text()).ast
    caps = native_capabilities()
    result = compile_semantic_pipeline(ast, caps.supported_strategies)
    assert any(c.strategy == "fused-filter-map-reduce" for c in result.strategies)
    assert all(c.strategy in caps.supported_strategies for c in result.strategies)

def test_unsupported_parallel_sort_is_not_selected_for_native_backend():
    ast = parse("""data people:
    a value 3
    b value 1
    c value 2
ranked = people sort by value
""").ast
    result = compile_semantic_pipeline(ast, native_capabilities().supported_strategies)
    assert all(c.strategy != "parallel-stable-sort" for c in result.strategies)
