from slang.execution_profile import ExecutionProfile, format_execution_profile
from slang.compiler_pipeline import compile_semantic_pipeline
from slang.core import parse


def test_reference_profile_is_conservative():
    p = ExecutionProfile.reference()
    assert p.cpu_cores == 1
    assert not p.allow_parallelism


def test_profile_rejects_invalid_values():
    try:
        ExecutionProfile(cpu_cores=0)
    except ValueError as exc:
        assert "cpu_cores" in str(exc)
    else:
        raise AssertionError("invalid profile accepted")


def test_profile_format_is_deterministic():
    text = format_execution_profile(ExecutionProfile(cpu_cores=8, allow_parallelism=True))
    assert "cpu_cores = 8" in text
    assert "allow_parallelism = yes" in text


def test_profile_attaches_to_compiler_pipeline():
    module = parse("data values:\n    a value 1\n    b value 2\nresult = values |> map value * 2\n")
    profile = ExecutionProfile(cpu_cores=8, allow_parallelism=True)
    result = compile_semantic_pipeline(module.ast, execution_profile=profile)
    assert result.execution_profile == profile


def test_profile_can_disable_parallel_backend_strategies():
    module = parse("data values:\n    a value 1\n    b value 2\nresult = values |> map value * 2\n")
    profile = ExecutionProfile(cpu_cores=8, allow_parallelism=False)
    result = compile_semantic_pipeline(module.ast, backend_parallelism=("sequential", "parallel-where-independent"), execution_profile=profile)
    assert all(c.profile != "parallel" for c in result.strategies)
