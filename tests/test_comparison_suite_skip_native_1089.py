from pathlib import Path
from types import SimpleNamespace

from slang import comparison_suite


def test_run_case_can_skip_native_execution(tmp_path, monkeypatch):
    slang = tmp_path / "case.sl"
    python = tmp_path / "case.py"
    cpp = tmp_path / "case.cpp"
    for path in (slang, python, cpp):
        path.write_text("source\n", encoding="utf-8")

    case = comparison_suite.ComparisonCase("skip-native", slang, python, cpp)
    outputs = iter(((0.01, "42"), (0.01, "42"), (0.01, "42")))
    monkeypatch.setattr(comparison_suite, "_run", lambda command: next(outputs))
    monkeypatch.setattr(
        comparison_suite.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stderr=""),
    )
    monkeypatch.setattr(
        comparison_suite,
        "_native",
        lambda case: (_ for _ in ()).throw(AssertionError("native must be skipped")),
    )

    result = comparison_suite.run_case(case, "c++", iterations=1, native=False)

    assert result["correctness"]["all_match"] is True
    assert result["native"]["available"] is False
    assert result["native"]["skipped"] is True


def test_report_labels_skipped_native_checks(tmp_path, monkeypatch):
    from slang import full_comparison_suite

    monkeypatch.setattr(full_comparison_suite, "OUT", tmp_path)
    case = {
        "name": "example",
        "source_lines": {"S-Lang": 1, "Python": 2, "C++": 3},
        "correctness": {"all_match": True},
        "median_seconds": {"S-Lang_interpreter": 0.1, "Python": 0.1, "C++": 0.1},
        "native": {"available": False, "skipped": True},
    }
    result = {
        "corpora": {"control": {"cases": [case]}, "real_world": {"cases": []}},
        "summary": {
            "correct": 1,
            "cases": 1,
            "source_lines_total": {"S-Lang": 1, "Python": 2, "C++": 3},
        },
    }

    full_comparison_suite.write_report(result)
    report = (tmp_path / "REPORT.md").read_text(encoding="utf-8")

    assert "| skipped |" in report
    assert "native checks were skipped" in report
