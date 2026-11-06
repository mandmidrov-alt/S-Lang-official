from slang.performance_suite import run_suite


def test_performance_stability_suite_is_deterministic():
    results = run_suite(2)
    assert len(results) == 3
    assert all(row["stable"] for row in results)
    assert all(row["interpreter_native_result_match"] for row in results)
