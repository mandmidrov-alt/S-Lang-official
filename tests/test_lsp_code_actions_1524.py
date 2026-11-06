from slang.core import parse
from slang.diagnostics import Diagnostic, DiagnosticSeverity, SourcePosition, SourceSpan
from slang.lsp_features import code_actions_for_diagnostics


def test_unknown_name_typo_quickfix_is_deterministic():
    program = parse("let value = 1\n")
    diagnostic = Diagnostic(
        DiagnosticSeverity.ERROR,
        "unknown name 'valui'",
        code="E2001",
        phase="semantic",
        span=SourceSpan(SourcePosition(2, 14), SourcePosition(2, 18)),
        data={"name": "valui"},
    )
    actions = code_actions_for_diagnostics(program, "let value = 1\n", "file:///tmp/fix.sl", (diagnostic,))
    assert len(actions) == 1
    assert actions[0]["kind"] == "quickfix"
    assert actions[0]["edit"]["changes"]["file:///tmp/fix.sl"][0]["newText"] == "value"


def test_distant_typo_does_not_produce_a_guess():
    program = parse("let value = 1\n")
    diagnostic = Diagnostic(
        DiagnosticSeverity.ERROR,
        "unknown name 'completely_different'",
        code="E2001",
        phase="semantic",
        span=SourceSpan(SourcePosition(2, 1), SourcePosition(2, 21)),
        data={"name": "completely_different"},
    )
    assert code_actions_for_diagnostics(program, "", "file:///tmp/fix.sl", (diagnostic,)) == ()
