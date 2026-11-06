from slang.stability_suite import run_suite


def test_pre_1_0_stability_suite_is_deterministic():
    results = run_suite()
    assert len(results) == 4
    assert all(row["stable"] for row in results)
    assert all(row["graph_stable"] for row in results)
    assert all(row["goal_stable"] for row in results)
    assert all(row["pipeline_stable"] for row in results)
