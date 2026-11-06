import pytest

from slang.core import parse, run, validate


def _run(source: str):
    program = parse(source)
    validate(program)
    run(program)
    return program


def test_to_number_invalid_text_explains_expected_format():
    with pytest.raises(RuntimeError) as error:
        _run('let value = to_number("12,5")\n')
    message = str(error.value)
    assert "cannot convert '12,5' to Number" in message
    assert "numeric text such as '12' or '3.5'" in message
    assert "decimal separator" in message


def test_to_number_valid_text_still_converts_integer_and_decimal():
    program = _run('let whole = to_number("12")\nlet fraction = to_number("3.5")\n')
    assert program._bindings["whole"] == 12
    assert program._bindings["fraction"] == 3.5


def test_json_parse_error_includes_location_and_repair_hint():
    with pytest.raises(RuntimeError) as error:
        _run('let value = json_parse("{bad json}")\n')
    message = str(error.value)
    assert "could not read valid JSON" in message
    assert "position" in message
    assert "Check quotes, commas, brackets" in message


def test_json_parse_valid_input_is_unchanged():
    program = _run('let value = json_parse("{\\"count\\": 2}")\n')
    assert program._bindings["value"] == {"count": 2}
