from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data


def test_duplicate_local_variable_has_structured_payload():
    result = diagnostics_for_source(
        'function f() -> Number:\n    let value = 1\n    let value = 2\n    return value\n',
        path='duplicate-variable.sl',
    )
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == 'E2000'
    assert diagnostic.data == {
        'name': 'value',
        'construct': 'duplicate_local_variable',
    }
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_duplicate_local_function_has_structured_payload():
    result = diagnostics_for_source(
        'function outer() -> Number:\n    function inner() -> Number:\n        return 1\n    function inner() -> Number:\n        return 2\n    return inner()\n',
        path='duplicate-function.sl',
    )
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == 'E2000'
    assert diagnostic.data == {
        'name': 'inner',
        'construct': 'duplicate_local_function',
    }
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()
