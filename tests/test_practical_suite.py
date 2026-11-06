from slang.practical_suite import run_suite

def test_practical_suite_semantics():
    results = run_suite()
    assert len(results) == 12
    assert all(row["semantic_match"] for row in results)
    assert all(row["source_lines"] > 0 for row in results)
    assert any("filter" in row["intent_operations"] for row in results)
    assert any("goal-path" in row["intent_operations"] for row in results)
    assert any(row["domain"] == "external data" for row in results)
    assert any(row["domain"] == "generic data" for row in results)
