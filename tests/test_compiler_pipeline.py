from slang.core import parse
from slang.compiler_pipeline import compile_semantic_pipeline, format_compiler_pipeline


def test_pipeline_connects_all_semantic_stages():
    p = parse("""
data people:
    Alice age 20
    Bob age 16
adults = people where age >= 18
ranked = adults sort by age
show ranked
""")
    result = compile_semantic_pipeline(p.ast)
    assert result.source_nodes >= result.optimized_nodes
    assert result.optimized_ir.nodes
    assert result.dependency_graph.edges is not None
    assert result.dependency_analysis.levels
    assert result.execution_plan.steps
    assert result.strategies


def test_pipeline_is_deterministic():
    source = """
data people:
    Alice age 20
    Bob age 16
adults = people where age >= 18
show adults
"""
    a = compile_semantic_pipeline(parse(source).ast)
    b = compile_semantic_pipeline(parse(source).ast)
    assert a.optimized_ir == b.optimized_ir
    assert a.dependency_graph == b.dependency_graph
    assert a.dependency_analysis == b.dependency_analysis
    assert a.execution_plan == b.execution_plan
    assert a.strategies == b.strategies


def test_pipeline_report_declares_backend_boundary():
    p = parse("""
data people:
    Alice age 20
show people
""")
    text = format_compiler_pipeline(compile_semantic_pipeline(p.ast))
    assert "planning = complete" in text
    assert "runtime_execution = not-invoked" in text
    assert "backend_lowering = separate-stage" in text
