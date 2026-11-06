from slang.core import parse, validate, run, parse_expr as core_parse_expr
from slang.semantic import infer, TypeEnv
from slang.types import NUMBER, TEXT


def parse_expr(src):
    return core_parse_expr(src)


def test_text_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('count_text("banana", "na")'), env) == NUMBER
    assert infer(parse_expr('remove_prefix_text("prefix-value", "prefix-")'), env) == TEXT
    assert infer(parse_expr('remove_suffix_text("value.txt", ".txt")'), env) == TEXT
    assert infer(parse_expr('reverse_text("abc")'), env) == TEXT


def test_text_runtime():
    p = parse('''let a = count_text("banana", "na")
let b = remove_prefix_text("prefix-value", "prefix-")
let c = remove_suffix_text("value.txt", ".txt")
let d = reverse_text("abc")
show a
show b
show c
show d
''')
    validate(p); run(p)


def test_text_edges():
    p = parse('''let a = count_text("aaaa", "aa")
let b = remove_prefix_text("value", "prefix-")
let c = remove_suffix_text("value", ".txt")
let d = reverse_text("")
show a
show b
show c
show d
''')
    validate(p); run(p)

    try:
        p = parse('let x = count_text("abc", "")\nshow x\n')
        validate(p); run(p)
    except (ValueError, RuntimeError):
        pass
    else:
        raise AssertionError("expected count_text empty-needle failure")
