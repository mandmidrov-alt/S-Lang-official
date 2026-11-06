from pathlib import Path
import pytest
from slang.core import parse, validate

ROOT = Path(__file__).resolve().parents[1]


def test_generic_record_function_composition_is_resolved_before_lowering():
    program = parse('''
record Box<T>:
    value: T

record Out<T>:
    value: T

function unwrap<T>(box: Box<T>) -> T:
    return box.value

function wrap<T>(box: Box<T>) -> Out<T>:
    return Out(unwrap(box))

let result = wrap(Box(42))
show result.value
''', ROOT)
    validate(program)


def test_generic_record_function_argument_mismatch_is_semantic_error():
    program = parse('''
record Box<T>:
    value: T

function unwrap<T>(box: Box<T>) -> T:
    return box.value

function need_number(value: Number) -> Number:
    return value

let result = need_number(unwrap(Box("wrong")))
''', ROOT)
    with pytest.raises(TypeError, match="need_number|argument 1"):
        validate(program)


def test_return_only_generic_is_rejected_before_lowering():
    program = parse('''
function impossible<T>() -> T:
    return 1
''', ROOT)
    with pytest.raises(TypeError, match="cannot be inferred from arguments"):
        validate(program)
