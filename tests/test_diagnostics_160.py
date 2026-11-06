from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data


def test_function_return_mismatch_has_structured_payload():
    bag = diagnostics_for_source('function f(x: Number) -> Text:\n    return x\n', path='example.sl')
    assert len(bag.diagnostics) == 1
    diagnostic = bag.diagnostics[0]
    assert diagnostic.code == 'E2000'
    assert diagnostic.data == {
        'expected_type': 'Text',
        'actual_type': 'Number',
        'construct': 'function_return',
    }
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()



def test_property_return_mismatch_has_structured_payload():
    source = '''property Circle.bad -> Number:
    return self.radius * 2

circle disk:
    radius 10 m
'''
    bag = diagnostics_for_source(source, path='property.sl')
    assert len(bag.diagnostics) == 1
    diagnostic = bag.diagnostics[0]
    assert diagnostic.code == 'E2000'
    assert diagnostic.data == {
        'expected_type': 'Number',
        'actual_type': 'Quantity<(0, 1, 0)>',
        'construct': 'property_return',
    }
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()
