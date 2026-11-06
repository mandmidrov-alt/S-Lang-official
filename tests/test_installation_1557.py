from slang.installation_suite import run_suite


def test_installation_suite_reports_a_complete_installed_workflow():
    result = run_suite()
    assert result["passed"] is True
    assert result["workflow"] == ["install", "init", "resolve", "lock", "check", "run", "native-build", "native-run"]
    assert any(step["step"] == "console-script" and step["passed"] for step in result["steps"])
