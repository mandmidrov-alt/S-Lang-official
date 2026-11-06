from slang.practical_suite import run_suite


def test_120_practical_corpus_covers_eight_real_task_shapes():
    results = run_suite()
    assert len(results) == 12
    assert all(row["semantic_match"] for row in results)
    assert all(row["source_lines"] >= 3 for row in results)
    assert all(row["intent_operations"] for row in results)


def test_120_practical_corpus_exposes_multiple_abstraction_levels():
    results = run_suite()
    domains = {row["domain"] for row in results}
    assert {"data processing", "graph planning", "constraint solving", "external data", "generic data"} <= domains
