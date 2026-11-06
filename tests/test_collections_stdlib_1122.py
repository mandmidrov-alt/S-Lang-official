from slang.core import parse, validate, run, parse_expr as core_parse_expr
from slang.semantic import infer, TypeEnv
from slang.types import NUMBER, TEXT, list_type


def parse_expr(src):
    return core_parse_expr(src)


def test_collection_slice_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('take([1, 2, 3], 2)'), env) == list_type(NUMBER)
    assert infer(parse_expr('skip(["a", "b"], 1)'), env) == list_type(TEXT)


def test_collection_slice_runtime():
    p = parse('''let a = take([1, 2, 3], 2)\nlet b = skip([1, 2, 3], 2)\nlet c = take([1, 2, 3], 10)\nlet d = skip([1, 2, 3], 10)\nshow a\nshow b\nshow c\nshow d\n''')
    validate(p); run(p)


def test_collection_slice_edges():
    p = parse('''let a = take([], 3)\nlet b = skip([], 3)\nlet c = take([1, 2], 0)\nlet d = skip([1, 2], 0)\nshow a\nshow b\nshow c\nshow d\n''')
    validate(p); run(p)

    for src in ('take([1, 2], 0 - 1)', 'skip([1, 2], 0 - 1)'):
        try:
            p = parse(f'let x = {src}\nshow x\n')
            validate(p); run(p)
        except (ValueError, RuntimeError):
            pass
        else:
            raise AssertionError('expected negative count failure')
