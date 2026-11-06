from slang.stdlib_runtime import (
    RuntimeExecutionContext,
    capture_runtime_trace,
    execute_registered_stdlib,
    runtime_execution_context,
)


def test_unified_context_collects_trace_summary_and_limits():
    with runtime_execution_context(max_events=4) as context:
        assert isinstance(context, RuntimeExecutionContext)
        execute_registered_stdlib("current_directory", [])
        execute_registered_stdlib("platform_name", [])
        assert context.event_count == 2
        assert context.summary.successful_count == 2
        assert context.effects == ("IO",)
        assert context.elapsed_ms >= 0


def test_nested_trace_capture_also_reaches_execution_context():
    with runtime_execution_context() as context:
        with capture_runtime_trace() as inner:
            execute_registered_stdlib("platform_name", [])
        assert len(inner) == 1
        assert context.event_count == 1
        assert context.summary.calls_by_name == (("platform_name", 1),)


def test_context_restores_previous_state():
    with runtime_execution_context() as outer:
        execute_registered_stdlib("platform_name", [])
        with runtime_execution_context() as inner:
            execute_registered_stdlib("current_directory", [])
            assert inner.event_count == 1
        assert outer.event_count == 1
        assert outer.summary.calls_by_name == (("platform_name", 1),)
