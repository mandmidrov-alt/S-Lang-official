from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data


def test_unknown_standalone_name_is_reported_with_structured_data():
    diagnostic = diagnostics_for_source("let result = missing_value\n", path="unknown.sl").diagnostics[0]
    assert diagnostic.code == "E2001"
    assert diagnostic.message == "unknown name 'missing_value'"
    assert diagnostic.data == {"name": "missing_value"}
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_unknown_name_inside_expression_is_reported_as_name_error():
    diagnostic = diagnostics_for_source("let result = missing_value + 1\n", path="unknown.sl").diagnostics[0]
    assert diagnostic.code == "E2001"
    assert diagnostic.data == {"name": "missing_value"}
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_declared_name_still_resolves():
    assert diagnostics_for_source("let value = 1\nlet result = value\n").diagnostics == ()


def test_unknown_name_suggests_a_close_declared_name():
    diagnostic = diagnostics_for_source(
        "let total = 4\nlet result = totl + 1\n", path="typo.sl"
    ).diagnostics[0]
    assert diagnostic.code == "E2001"
    assert diagnostic.message == "unknown name 'totl'"
    assert diagnostic.hint == "did you mean 'total'? Check the spelling or declare 'totl' before using it."


def test_unknown_name_does_not_suggest_unrelated_names():
    diagnostic = diagnostics_for_source(
        "let result = qzxv_missing\n", path="unknown.sl"
    ).diagnostics[0]
    assert diagnostic.code == "E2001"
    assert diagnostic.hint == "declare the name before using it"
