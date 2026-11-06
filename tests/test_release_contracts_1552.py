from slang.release_suite import run_suite


def test_release_suite_checks_compiler_artifact_and_stdlib_contracts():
    result = run_suite()
    assert result["checks"]["compiler_artifact_contract"] is True
    assert result["checks"]["stdlib_contract"] is True
    assert result["counts"]["stdlib_entries"] > 0
    assert result["counts"]["stdlib_contract_errors"] == []
