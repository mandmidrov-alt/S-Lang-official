import pytest

from slang.e2e_extended_suite import run_suite


@pytest.fixture(scope="module")
def expanded_e2e_result():
    """Run the CLI-heavy acceptance matrix once for all assertions in this module."""
    return run_suite()


def test_expanded_end_to_end_matrix_passes(expanded_e2e_result):
    result = expanded_e2e_result
    assert result["summary"]["release_blocking"] is True
    assert result["summary"]["passed"] == result["summary"]["cases"], [
        case for case in result["cases"] if case["status"] != "passed"
    ]


def test_expanded_matrix_contains_distinct_language_and_runtime_paths(expanded_e2e_result):
    names = {case["name"] for case in expanded_e2e_result["cases"]}
    assert {
        "collection_utilities_125.sl",
        "closures.sl",
        "generic_collections.sl",
        "json_1294.sl",
        "datetime_1297.sl",
        "fused_reduce.sl",
    } <= names


def test_expanded_case_preserves_cli_failure_diagnostics(monkeypatch):
    import subprocess
    import slang.e2e_extended_suite as suite

    monkeypatch.setattr(
        suite,
        "_cli",
        lambda *args: subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout="partial output",
            stderr="simulated timeout diagnostic",
        ),
    )
    result = suite._run_example("generic_collections.sl", "expected")
    assert result["status"] == "failed"
    assert result["timed_out"] is True
    assert result["stdout_tail"] == "partial output"
    assert result["stderr_tail"] == "simulated timeout diagnostic"
    assert isinstance(result["elapsed_seconds"], float)
