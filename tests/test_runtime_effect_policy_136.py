from slang.stdlib_runtime import (
    RuntimeCapabilityError,
    capture_runtime_trace,
    registered_stdlib_capability,
    runtime_effect_policy,
    runtime_execution_profile,
)
from slang.plan_runtime_support import get_stdlib_function


def test_runtime_effect_policy_allows_pure_and_denies_io():
    assert registered_stdlib_capability("sqrt") == "pure"
    assert registered_stdlib_capability("run_process") == "process"
    with runtime_effect_policy(allowed_effects={"pure"}, allowed_capabilities={"pure"}):
        from slang.stdlib_runtime import execute_registered_stdlib
        ok, value = execute_registered_stdlib("sqrt", [9])
        assert ok and value == 3
        try:
            execute_registered_stdlib("run_process", ["printf nope"])
            assert False, "expected RuntimeCapabilityError"
        except RuntimeCapabilityError:
            pass


def test_runtime_execution_profile_blocks_io_at_runtime_boundary():
    fn = get_stdlib_function("current_directory")
    with runtime_execution_profile("safe"):
        with capture_runtime_trace() as events:
            try:
                from slang.stdlib_runtime import execute_registered_stdlib
                execute_registered_stdlib("current_directory", [])
                assert False, "expected RuntimeCapabilityError"
            except RuntimeCapabilityError:
                pass
        assert events[-1].error_type == "RuntimeCapabilityError"


def test_normal_profile_restores_after_nested_safe_profile():
    fn = get_stdlib_function("sqrt")
    with runtime_execution_profile("normal"):
        assert fn.evaluator([16]) == 4
        with runtime_execution_profile("safe"):
            assert fn.evaluator([25]) == 5
        assert fn.evaluator([36]) == 6


def test_custom_capability_policy_allows_runtime_but_not_process():
    from slang.stdlib_runtime import execute_registered_stdlib
    with runtime_effect_policy(allowed_capabilities={"runtime"}, allowed_effects={"IO"}):
        ok, value = execute_registered_stdlib("platform_name", [])
        assert ok and isinstance(value, str)
        try:
            execute_registered_stdlib("run_process", ["echo denied"])
            assert False, "expected RuntimeCapabilityError"
        except RuntimeCapabilityError:
            pass
