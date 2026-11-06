from slang.stdlib_runtime import capture_runtime_trace, execute_registered_stdlib, summarize_runtime_trace


def test_runtime_summary_counts_calls_and_effects():
    with capture_runtime_trace() as events:
        execute_registered_stdlib("normalize_whitespace", ["  a  "])
        execute_registered_stdlib("current_directory", [])
        execute_registered_stdlib("normalize_whitespace", ["  b  "])
    summary = summarize_runtime_trace(events)
    assert summary.event_count == 3
    assert summary.successful_count == 3
    assert summary.failed_count == 0
    assert summary.effects == ("IO", "pure")
    assert summary.calls_by_name == (("current_directory", 1), ("normalize_whitespace", 2))


def test_runtime_summary_counts_failures():
    with capture_runtime_trace() as events:
        try:
            execute_registered_stdlib("add_days_datetime", ["bad", 1])
        except RuntimeError:
            pass
    summary = summarize_runtime_trace(events)
    assert summary.event_count == 1
    assert summary.successful_count == 0
    assert summary.failed_count == 1
