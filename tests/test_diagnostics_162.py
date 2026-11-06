from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data


def test_if_statement_condition_error_has_structured_payload():
    diagnostic = diagnostics_for_source(
        'function f() -> Number:\n    if 1:\n        return 1\n    else:\n        return 2\n',
        path='if-condition.sl',
    ).diagnostics[0]
    assert diagnostic.code == 'E2006'
    assert diagnostic.data == {
        'expected_type': 'Boolean',
        'actual_type': 'Number',
        'construct': 'if_statement',
    }
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_if_statement_branch_mismatch_has_structured_payload():
    diagnostic = diagnostics_for_source(
        'let x = if true then 1 else "text"\n',
        path='if-branches.sl',
    ).diagnostics[0]
    assert diagnostic.code == 'E2000'
    assert diagnostic.data == {
        'expected_type': 'Number',
        'actual_type': 'Text',
        'construct': 'conditional',
    }
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()
