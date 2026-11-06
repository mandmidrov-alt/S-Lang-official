from slang.diagnostics import diagnostics_for_source


def test_argument_type_hint_names_expected_and_actual_types():
    d = diagnostics_for_source('let x = join(1, "-")\n').diagnostics[0]
    assert d.code == "E2004"
    assert d.data["expected_type"] == "List<Text>"
    assert d.data["actual_type"] == "Number"
    assert "Argument 1 of 'join' expects List<Text>, but received Number" in d.hint
    assert "convert it before this call" in d.hint


def test_condition_type_hint_explains_boolean_requirement():
    d = diagnostics_for_source('let x = if 1 then 2 else 3\n').diagnostics[0]
    assert d.code == "E2006"
    assert "must be Boolean" in d.hint
    assert "type Number" in d.hint


def test_binary_type_hint_explains_incompatible_operands():
    d = diagnostics_for_source('let x = 1 + "text"\n').diagnostics[0]
    assert d.code == "E2000"
    assert "Operator '+' cannot combine Number and Text" in d.hint


def test_wrong_argument_count_hint_is_actionable():
    d = diagnostics_for_source('let x = len(1, 2)\n').diagnostics[0]
    assert d.code == "E2003"
    assert "'len' expects 1 argument(s), but 2 were provided" in d.hint


def test_unknown_function_keeps_existing_generic_hint():
    d = diagnostics_for_source('let x = totally_unrelated(1)\n').diagnostics[0]
    assert d.code == "E2002"
    assert d.hint == "check the function name and available imports"
