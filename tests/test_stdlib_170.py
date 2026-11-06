from slang.core import parse, parse_expr, validate, run
from slang.semantic import TypeEnv, infer
from slang.types import TEXT, list_type


def test_stdlib_signatures_are_available():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('split(upper(trim(" a,b ")), ",")'), env) == list_type(TEXT)


def test_stdlib_math_and_text_runtime():
    p = parse('result = sqrt(9) + floor(2.9)')
    validate(p)
    run(p)
    assert p._bindings.get("result") == 5


def test_stdlib_json_roundtrip_runtime():
    p = parse('result = json_stringify(json_parse("{\\"x\\":1}"))')
    validate(p)
    run(p)
    assert p._bindings.get("result") == '{"x":1}'


def test_stdlib_text_composition_runtime():
    p = parse('result = split(upper(trim(" a,b ")), ",")')
    validate(p)
    run(p)
    assert p._bindings.get("result") == ["A", "B"]
