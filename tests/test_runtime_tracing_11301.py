from slang.stdlib_runtime import RuntimeTraceEvent, capture_runtime_trace, execute_registered_stdlib


def test_capture_runtime_trace_records_success():
    with capture_runtime_trace() as events:
        handled, result = execute_registered_stdlib("normalize_whitespace", ["  a   b  "])
    assert handled is True
    assert result == "a b"
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, RuntimeTraceEvent)
    assert event.name == "normalize_whitespace"
    assert event.effect == "pure"
    assert event.argument_count == 1
    assert event.success is True
    assert event.error_type is None
    assert event.duration_ms >= 0


def test_capture_runtime_trace_records_io_effect():
    with capture_runtime_trace() as events:
        handled, result = execute_registered_stdlib("current_directory", [])
    assert handled is True
    assert isinstance(result, str)
    assert len(events) == 1
    assert events[0].name == "current_directory"
    assert events[0].effect == "IO"
    assert events[0].success is True


def test_capture_runtime_trace_records_normalized_error():
    with capture_runtime_trace() as events:
        try:
            execute_registered_stdlib("add_days_datetime", ["not-a-date", 1])
        except RuntimeError as exc:
            assert "add_days_datetime failed" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
    assert len(events) == 1
    assert events[0].name == "add_days_datetime"
    assert events[0].success is False
    assert events[0].error_type == "ValueError"


def test_trace_does_not_leak_between_contexts():
    with capture_runtime_trace() as first:
        execute_registered_stdlib("normalize_whitespace", ["x"])
    with capture_runtime_trace() as second:
        execute_registered_stdlib("normalize_whitespace", ["y"])
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].name == second[0].name == "normalize_whitespace"


def test_capture_runtime_trace_records_registered_argument_count_error():
    with capture_runtime_trace() as events:
        try:
            execute_registered_stdlib("normalize_whitespace", [])
        except TypeError as exc:
            assert "expects 1 argument(s), got 0" in str(exc)
        else:
            raise AssertionError("expected TypeError")
    assert len(events) == 1
    assert events[0].name == "normalize_whitespace"
    assert events[0].argument_count == 0
    assert events[0].success is False
    assert events[0].error_type == "TypeError"


def test_capture_runtime_trace_records_legacy_boundary_argument_count_error():
    from slang.stdlib_runtime import execute_runtime_call

    with capture_runtime_trace() as events:
        try:
            execute_runtime_call(
                "current_directory",
                ["unexpected"],
                lambda args: None,
                expected_args=0,
            )
        except TypeError as exc:
            assert "expects 0 argument(s), got 1" in str(exc)
        else:
            raise AssertionError("expected TypeError")
    assert len(events) == 1
    assert events[0].name == "current_directory"
    assert events[0].argument_count == 1
    assert events[0].success is False
    assert events[0].error_type == "TypeError"
