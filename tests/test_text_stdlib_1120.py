from slang.core import parse, validate, run, parse_expr as core_parse_expr
from slang.semantic import infer, TypeEnv
from slang.types import NUMBER, TEXT

def parse_expr(src):
    return core_parse_expr(src)

def test_text_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('length_text("hello")'), env) == NUMBER
    assert infer(parse_expr('substring_text("hello", 1, 4)'), env) == TEXT
    assert infer(parse_expr('char_at_text("hello", 1)'), env) == TEXT
    assert infer(parse_expr('pad_left_text("7", 3, "0")'), env) == TEXT
    assert infer(parse_expr('pad_right_text("7", 3, "0")'), env) == TEXT

def test_text_runtime():
    p = parse('''let a = length_text("hello")
let b = substring_text("hello", 1, 4)
let c = char_at_text("hello", 1)
let d = pad_left_text("7", 3, "0")
let e = pad_right_text("7", 3, "0")
show a
show b
show c
show d
show e
''')
    validate(p); run(p)

def test_text_bounds():
    for src in ['substring_text("abc", 0 - 1, 2)', 'substring_text("abc", 2, 1)', 'char_at_text("abc", 3)', 'pad_left_text("x", 0 - 1, "0")', 'pad_right_text("x", 2, "")']:
        try:
            p = parse(f'let x = {src}\nshow x\n'); validate(p); run(p)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError(f"expected validation/runtime failure for {src}")
