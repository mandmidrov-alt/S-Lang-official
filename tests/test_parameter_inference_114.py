import pytest
from slang.core import parse, validate


def test_untyped_parameter_inferred_from_call_site():
    p = parse('''function double(x) -> Number:\n    return x + x\n\nlet value = double(7)\nshow value\n''')
    validate(p)


def test_untyped_parameter_inferred_from_typed_callee():
    p = parse('''function increment(x) -> Number:\n    return add_one(x)\n\nfunction add_one(x: Number) -> Number:\n    return x + 1\n\nlet value = increment(7)\n''')
    validate(p)


def test_untyped_parameter_without_evidence_is_rejected():
    p = parse('''function identity(x):\n    return x\n''')
    with pytest.raises(TypeError, match="cannot infer parameter type"):
        validate(p)


def test_untyped_parameter_conflicting_calls_are_rejected():
    p = parse('''function identity(x) -> Number:\n    return x\n\nlet a = identity(1)\nlet b = identity("text")\n''')
    with pytest.raises(TypeError, match="conflicting call-site types"):
        validate(p)


def test_typed_parameters_remain_unchanged():
    p = parse('''function double(x: Number) -> Number:\n    return x + x\n\nlet value = double(7)\n''')
    validate(p)
