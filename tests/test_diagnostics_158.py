from slang.diagnostics import diagnostics_for_source


def test_unknown_function_has_structured_data():
    d = diagnostics_for_source('let x = missing(1)\n').diagnostics[0]
    assert d.code == 'E2002'
    assert d.data == {'function': 'missing'}


def test_wrong_arity_has_structured_data():
    d = diagnostics_for_source('let x = len(1, 2)\n').diagnostics[0]
    assert d.code == 'E2003'
    assert d.data['function'] == 'len'
    assert d.data['expected_arity'] == 1
    assert d.data['actual_arity'] == 2


def test_argument_type_has_structured_data():
    d = diagnostics_for_source('let x = join(1, "-")\n').diagnostics[0]
    assert d.code == 'E2004'
    assert d.data['function'] == 'join'
    assert d.data['argument'] == 1
    assert d.data['expected_type'] == 'List<Text>'
    assert d.data['actual_type'] == 'Number'


def test_binary_type_error_has_operator_and_operand_types():
    d = diagnostics_for_source('let x = 1 + "text"\n').diagnostics[0]
    assert d.code == 'E2000'
    assert d.data['operator'] == '+'
    assert d.data['left_type'] == 'Number'
    assert d.data['right_type'] == 'Text'


def test_condition_type_has_expected_and_actual_type():
    d = diagnostics_for_source('let x = if 1 then 2 else 3\n').diagnostics[0]
    assert d.code == 'E2006'
    assert d.data['expected_type'] == 'Boolean'
    assert d.data['actual_type'] == 'Number'
