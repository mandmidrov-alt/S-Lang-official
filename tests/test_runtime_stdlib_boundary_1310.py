from slang.stdlib_runtime import (
    RuntimeCapabilityError,
    capture_runtime_trace,
    execute_runtime_call,
    runtime_call_metadata,
    runtime_effect_policy,
)


def test_runtime_call_metadata_uses_registry_and_catalog():
    assert runtime_call_metadata("sqrt") == ("pure", "pure")
    assert runtime_call_metadata("read_text") == ("IO", "filesystem")
    assert runtime_call_metadata("run_process") == ("IO", "process")


def test_catalog_call_uses_common_permission_and_trace_boundary():
    with runtime_effect_policy(allowed_effects={"pure"}, allowed_capabilities={"pure"}):
        with capture_runtime_trace() as events:
            try:
                execute_runtime_call("run_process", ["echo denied"], lambda _: None, expected_args=1)
                assert False, "expected RuntimeCapabilityError"
            except RuntimeCapabilityError:
                pass
        assert events[-1].name == "run_process"
        assert events[-1].error_type == "RuntimeCapabilityError"
        assert events[-1].success is False


def test_catalog_call_success_is_traced():
    with capture_runtime_trace() as events:
        handled, value = execute_runtime_call("run_process", ["echo ok"], lambda _: ["0", "ok\n", ""], expected_args=1)
    assert handled and value[0] == "0"
    assert events[-1].success is True
    assert events[-1].effect == "IO"
