from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data


def test_invalid_field_payload_matches_schema():
    diagnostic = diagnostics_for_source('entity Planet:\n    mass: kg\n\nlet earth = Planet(5 kg)\nshow earth.velocity\n', path='field.sl').diagnostics[0]
    assert diagnostic.code == 'E2005'
    assert diagnostic.data is not None
    assert {'field', 'base_type'} <= set(diagnostic.data)
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_conditional_branch_mismatch_payload_matches_schema():
    diagnostic = diagnostics_for_source('let x = if true then 1 else "text"\n', path='branch.sl').diagnostics[0]
    assert diagnostic.code == 'E2000'
    assert diagnostic.data is not None
    assert diagnostic.data['expected_type'] == 'Number'
    assert diagnostic.data['actual_type'] == 'Text'
    assert diagnostic.data['construct'] == 'conditional'
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_json_keeps_schema_and_payload_for_type_error():
    diagnostic = diagnostics_for_source('let x = 1 + "text"\n', path='operator.sl').to_dict()[0]
    assert diagnostic['code'] == 'E2000'
    assert diagnostic['schema']['fields']
    assert diagnostic['data']['operator'] == '+'
    assert diagnostic['data']['left_type'] == 'Number'
    assert diagnostic['data']['right_type'] == 'Text'
