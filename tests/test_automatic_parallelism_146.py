from slang.compiler_pipeline import compile_semantic_pipeline
from slang.execution_profile import ExecutionProfile
from slang.core import parse


def _module(count=3):
    rows = "".join(f"    a{i} value {i}\n" for i in range(count))
    return parse("data values:\n" + rows + "result = values |> map value * 2\n").ast


def test_one_core_forces_sequential_even_when_parallelism_is_allowed():
    result = compile_semantic_pipeline(
        _module(100),
        backend_memory_models=("linear-buffer",),
        backend_orderings=("source-order", "dependency-ordered"),
        backend_parallelism=("sequential", "parallel-where-independent"),
        backend_materialization=("backend-defined",),
        execution_profile=ExecutionProfile(cpu_cores=1, allow_parallelism=True),
    )
    assert all(c.profile != "parallel" for c in result.strategies)


def test_multiple_cores_make_parallelism_eligible():
    result = compile_semantic_pipeline(
        _module(100),
        backend_memory_models=("linear-buffer",),
        backend_orderings=("source-order", "dependency-ordered"),
        backend_parallelism=("sequential", "parallel-where-independent"),
        backend_materialization=("backend-defined",),
        execution_profile=ExecutionProfile(cpu_cores=4, allow_parallelism=True),
    )
    assert any(c.profile == "parallel" for c in result.strategies)


def test_profile_cpu_count_is_part_of_preferences():
    p = ExecutionProfile(cpu_cores=8, allow_parallelism=True)
    prefs = dict(p.preferences())
    assert prefs["cpu_cores"] == 8.0


def test_parallel_choice_is_deterministic_for_same_profile():
    profile = ExecutionProfile(cpu_cores=8, allow_parallelism=True)
    kwargs = dict(backend_parallelism=("sequential", "parallel-where-independent"), execution_profile=profile)
    a = compile_semantic_pipeline(_module(), **kwargs)
    b = compile_semantic_pipeline(_module(), **kwargs)
    assert a.strategies == b.strategies
    assert a.selected_execution_plan == b.selected_execution_plan


def test_explanation_exposes_parallelism_policy():
    result = compile_semantic_pipeline(
        _module(),
        backend_memory_models=("linear-buffer",),
        backend_orderings=("source-order", "dependency-ordered"),
        backend_parallelism=("sequential", "parallel-where-independent"),
        backend_materialization=("backend-defined",),
        execution_profile=ExecutionProfile(cpu_cores=4, allow_parallelism=True),
    )
    assert "eligible-above-one-core" in __import__("slang.explainability", fromlist=["format_execution_explanation"]).format_execution_explanation(result.execution_explanation)
