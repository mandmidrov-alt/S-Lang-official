from slang.expressiveness_suite import run_suite, gap_report


def test_expressiveness_suite_runs_all_cases():
    results = run_suite()
    assert len(results) == 6
    assert all(row["semantic_result_available"] for row in results)
    assert all(row["slang_lines"] > 0 for row in results)
    assert all(row["reference_lines"] > row["slang_lines"] for row in results)


def test_expressiveness_gaps_are_explicit():
    gaps = gap_report()
    assert any(row["area"] == "network I/O" and row["status"] == "not implemented" for row in gaps)
    assert any(row["area"] == "general concurrency" for row in gaps)
