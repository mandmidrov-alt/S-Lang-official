from slang.stateful_suite import run_suite


def test_stateful_suite_passes():
    results = run_suite()
    assert len(results) == 2
    assert all(row["semantic_match"] for row in results)


def test_stateful_suite_uses_nested_transition_logic():
    results = run_suite()
    branching = next(row for row in results if row["name"] == "branching-state")
    assert branching["actual"] == ["show = [1, 2, 4, 8, 16, 17, 18, 19, 20, 21]"]
