from slang.core import parse, validate
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.selected_execution_plan import format_selected_execution_plan


def compile_source(source, **kwargs):
    p = parse(source)
    validate(p)
    return compile_semantic_pipeline(p.ast, **kwargs)


def test_selected_plan_binds_every_node():
    result = compile_source("""
let values = [1, 2, 3, 4]
result = values |> where >= 2 |> map * 2 |> sum
""")
    plan = result.selected_execution_plan
    assert plan.operation_count == len(result.strategies)
    assert [s.node for s in plan.steps] == [c.node for c in result.strategies]
    assert all(s.strategy for s in plan.steps)


def test_selected_plan_is_deterministic():
    source = """
let values = [1, 2, 3, 4]
result = values |> where >= 2 |> map * 2
"""
    a = compile_source(source).selected_execution_plan
    b = compile_source(source).selected_execution_plan
    assert a == b
    assert a.deterministic


def test_selected_plan_contains_resource_contract():
    result = compile_source("""
let values = [1, 2, 3]
result = values |> map * 2
""")
    step = result.selected_execution_plan.steps[-1]
    assert step.memory_model
    assert step.ordering
    assert step.parallelism
    assert step.materialization


def test_selected_plan_respects_execution_profile():
    from slang.execution_profile import ExecutionProfile
    profile = ExecutionProfile(cpu_cores=4, allow_parallelism=True)
    result = compile_source(
        """
let values = [1, 2, 3, 4]
result = values |> map * 2
""",
        execution_profile=profile,
    )
    assert result.selected_execution_plan.execution_profile == profile


def test_selected_plan_formatter_exposes_backend_artifact():
    result = compile_source("let result = 2 + 3")
    text = format_selected_execution_plan(result.selected_execution_plan)
    assert "selected.execution.plan" in text
    assert "strategy=" in text
    assert "resources =" in text
    assert "backend_input = explicit-selected-strategies" in text
