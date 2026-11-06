from slang.stress_suite import run_suite


def test_practical_stress_suite_is_semantically_closed():
    results = run_suite()
    assert len(results) == 5
    assert all(row["semantic_match"] for row in results)
    assert all(row["required_kinds_present"] for row in results)
    assert sum(row["source_lines"] for row in results) == 67
    assert sum(row["node_count"] for row in results) == 17
