from slang.real_world_suite import run_suite


def test_real_world_suite_semantics():
    result = run_suite(iterations=1)
    assert result["summary"]["cases"] == 7
    assert result["summary"]["all_correct"]
    assert result["summary"]["correct"] == 7
    assert all(row["correctness"]["all_match"] for row in result["cases"])
    assert all(all(value > 0 for value in row["source_lines"].values()) for row in result["cases"])
