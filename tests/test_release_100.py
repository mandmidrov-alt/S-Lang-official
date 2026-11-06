from slang.release_suite import run_suite


def test_release_semantic_acceptance_suite_is_ready():
    result = run_suite()
    assert result["release_ready"] is True
    assert all(result["checks"].values())
