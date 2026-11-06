from pathlib import Path
import json
import subprocess
import sys

from slang.diagnostics import DiagnosticSeverity, diagnostics_for_source, format_diagnostics

ROOT = Path(__file__).resolve().parents[1]


def test_valid_source_has_no_diagnostics():
    source = "state x = 1\nshow x\n"
    bag = diagnostics_for_source(source, path="example.sl")
    assert bag.diagnostics == ()
    assert not bag.has_errors


def test_parse_diagnostic_has_source_location():
    source = "state x = (1 + )\n"
    bag = diagnostics_for_source(source, path="broken.sl")
    assert len(bag.diagnostics) == 1
    diagnostic = bag.diagnostics[0]
    assert diagnostic.severity == DiagnosticSeverity.ERROR
    assert diagnostic.phase == "parse"
    assert diagnostic.code == "E1000"
    assert diagnostic.span is not None
    assert diagnostic.span.start.line == 1
    rendered = format_diagnostics(bag.diagnostics, source)
    assert "broken.sl:1:" in rendered
    assert "^" in rendered


def test_semantic_diagnostic_is_distinguished_from_parse():
    source = "state x = true + 1\nshow x\n"
    bag = diagnostics_for_source(source, path="semantic.sl")
    assert len(bag.diagnostics) == 1
    diagnostic = bag.diagnostics[0]
    assert diagnostic.phase == "semantic"
    assert diagnostic.code == "E2000"


def test_cli_json_diagnostics_are_stable(tmp_path):
    source = tmp_path / "broken.sl"
    source.write_text("state x = (1 + )\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "slang.cli", "diagnose", str(source), "--json"],
        cwd=ROOT, text=True, capture_output=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["error_count"] == 1
    assert payload["diagnostics"][0]["code"] == "E1000"
    assert payload["diagnostics"][0]["phase"] == "parse"
    assert payload["diagnostics"][0]["location"]["line"] == 1

def test_semantic_diagnostic_has_related_operand_spans_and_hint():
    source = 'let first = 1\nlet second = first + "text"\n'
    bag = diagnostics_for_source(source, path="example.sl")
    diagnostic = bag.diagnostics[0]
    assert diagnostic.code == "E2000"
    assert len(diagnostic.related) == 2
    assert diagnostic.related[0].label == "left operand"
    assert diagnostic.related[1].label == "right operand"
    assert diagnostic.hint == "Operator '+' cannot combine Number and Text. Use compatible values or convert one operand."
    payload = diagnostic.to_dict()
    assert payload["related"][0]["label"] == "left operand"
    assert payload["hint"]
