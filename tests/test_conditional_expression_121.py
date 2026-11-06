from pathlib import Path
from slang.core import parse_expr, parse_file, validate, run, show_expr_value
from slang.ast import Conditional

ROOT = Path(__file__).resolve().parents[1]


def test_121_conditional_expression_parses_and_nests():
    expr = parse_expr('if score >= 90 then "excellent" else if score >= 75 then "good" else "basic"')
    assert isinstance(expr, Conditional)
    assert isinstance(expr.else_expr, Conditional)


def test_121_conditional_expression_works_in_function_return():
    program = parse_file(ROOT / 'examples/conditional_expression.sl')
    validate(program)
    run(program)
    assert show_expr_value(program, program.show_exprs[0]) == 'good'


def test_121_conditional_expression_is_type_checked():
    bad = ROOT / 'examples/_bad_conditional_121.sl'
    bad.write_text('let x = if true then 1 else "text"\nshow x\n', encoding='utf-8')
    try:
        program = parse_file(bad)
        try:
            validate(program)
        except TypeError as exc:
            assert 'conditional branches' in str(exc)
        else:
            raise AssertionError('incompatible conditional branches were accepted')
    finally:
        bad.unlink(missing_ok=True)
