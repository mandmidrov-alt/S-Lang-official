from slang.core import parse, validate, run
import pytest


def test_pipeline_can_compose_functions_without_binding():
    p = parse('\nfunction double(x: Number) -> Number:\n    return x * 2\nfunction increment(x: Number) -> Number:\n    return x + 1\nlet values = [1, 2, 3]\nresult = values |> map compose(double, increment)\nshow result\n')
    validate(p); run(p)
    assert p._collections['result'] == [4, 6, 8]


def test_pipeline_composition_can_be_chained_without_intermediate_let():
    p = parse('\nfunction double(x: Number) -> Number:\n    return x * 2\nfunction increment(x: Number) -> Number:\n    return x + 1\nfunction negate(x: Number) -> Number:\n    return 0 - x\nlet values = [1, 2]\nresult = values |> map compose(double, increment) |> map negate\nshow result\n')
    validate(p); run(p)
    assert p._collections['result'] == [-4, -6]


def test_pipeline_composition_preserves_function_argument_identity():
    p = parse('\nfunction double(x: Number) -> Number:\n    return x * 2\nfunction increment(x: Number) -> Number:\n    return x + 1\nresult = compose(double, increment)\n')
    validate(p); run(p)
    assert p._bindings['result']([3]) == 8


def test_pipeline_composition_rejects_incompatible_functions():
    p = parse('\nfunction as_text(x: Number) -> Text:\n    return "x"\ndata values:\n    a value 1\nresult = values |> map compose(as_text, as_text)\n')
    with pytest.raises(TypeError, match='compose type mismatch'):
        validate(p)
