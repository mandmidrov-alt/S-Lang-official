from slang.core import parse, parse_expr, run, show_expr_value, validate
from slang.semantic import TypeEnv, infer
from slang.types import NUMBER
import pytest


def test_extended_numeric_signatures():
    env = TypeEnv({}, {}, {})
    for src in ('exp2_number(3)', 'cbrt_number(8)', 'log10_number(100)', 'log2_number(8)'):
        assert infer(parse_expr(src), env) == NUMBER


def test_extended_numeric_runtime():
    p = parse('''let a = exp2_number(3)
let b = cbrt_number(0 - 8)
let c = log10_number(100)
let d = log2_number(8)
show a
show b
show c
show d
''')
    validate(p); run(p)
    values = [float(show_expr_value(p, x)) for x in p.show_exprs]
    assert values == pytest.approx([8.0, -2.0, 2.0, 3.0], rel=1e-12)


def test_log_domain_validation():
    for src in ('log10_number(0)', 'log2_number(0)', 'log10_number(0 - 1)'):
        p = parse(f'let x = {src}\nshow x\n')
        validate(p)
        with pytest.raises((ValueError, RuntimeError)):
            run(p)
