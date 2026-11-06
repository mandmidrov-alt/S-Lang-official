from slang.rc_stability_suite import run_suite


def test_release_candidate_stability_suite_passes():
    result = run_suite()
    assert result["release_candidate"] is True
    assert result["passed"] is True
    assert all(result["checks"].values())
    assert result["repeated_e2e"]["runs"] == 3
    assert result["repeated_e2e"]["deterministic_report"] is True
    assert len(set(result["repeated_e2e"]["fingerprints"])) == 1
