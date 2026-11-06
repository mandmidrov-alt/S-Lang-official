import pytest

from slang.e2e_suite import run_suite


@pytest.fixture(scope="module")
def e2e_result():
    """Run the CLI-heavy release scenarios once for this test module."""
    return run_suite()


def test_end_to_end_release_scenarios_pass(e2e_result):
    result = e2e_result
    assert result["summary"]["release_blocking"] is True
    assert result["summary"]["passed"] >= 4


def test_end_to_end_covers_runtime_package_native_and_artifact_paths(e2e_result):
    result = e2e_result
    names = {case["name"] for case in result["cases"]}
    assert {
        "reference-data-pipeline",
        "stdlib-text-workflow",
        "transitive-package-project",
        "native-fused-reduction",
        "persisted-native-artifact",
    } <= names
