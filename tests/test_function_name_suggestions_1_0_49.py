from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data


def test_unknown_function_suggests_a_close_standard_library_function():
    diagnostic = diagnostics_for_source(
        "let result = sum_numbes([1, 2, 3])\n", path="typo_function.sl"
    ).diagnostics[0]
    assert diagnostic.code == "E2002"
    assert diagnostic.message == "unknown function 'sum_numbes'"
    assert diagnostic.hint == (
        "did you mean 'sum_numbers'? Check the function name "
        "and whether its module is imported."
    )
    assert diagnostic.data == {"function": "sum_numbes"}
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_unknown_function_does_not_suggest_unrelated_function():
    diagnostic = diagnostics_for_source(
        "let result = qzxv_mystery([1, 2, 3])\n", path="unknown_function.sl"
    ).diagnostics[0]
    assert diagnostic.code == "E2002"
    assert diagnostic.message == "unknown function 'qzxv_mystery'"
    assert diagnostic.hint == "check the function name and available imports"
