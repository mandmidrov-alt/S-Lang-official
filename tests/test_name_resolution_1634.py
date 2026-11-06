from slang.diagnostics import diagnostics_for_source, validate_diagnostic_data
from slang.core import parse, validate, run


def test_unknown_name_inside_nested_function_has_structured_diagnostic():
    source = '''
function outer(value: Number) -> Function<Number, Number>:
    function inner(step: Number) -> Number:
        return value + missing_step
    return inner
'''
    result = diagnostics_for_source(source, path="nested-name.sl")
    diagnostic = next(d for d in result.diagnostics if d.code == "E2001")
    assert diagnostic.data == {"name": "missing_step"}
    assert validate_diagnostic_data(diagnostic.code, diagnostic.data) == ()


def test_nested_function_can_resolve_captured_parameter():
    source = '''
function outer(value: Number) -> Function<Number, Number>:
    function inner(step: Number) -> Number:
        return value + step
    return inner
let add_five = outer(5)
result = add_five(3)
'''
    program = parse(source)
    validate(program)
    run(program)
    assert program._bindings["result"] == 8


def test_unknown_name_does_not_mask_valid_outer_binding():
    source = '''
function outer(value: Number) -> Number:
    function inner(step: Number) -> Number:
        return value + step
    return inner(2)
result = outer(5)
'''
    result = diagnostics_for_source(source, path="outer-binding.sl")
    assert not any(d.code == "E2001" for d in result.diagnostics)
