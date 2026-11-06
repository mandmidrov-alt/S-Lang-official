import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value
from slang.ast import ReduceOp


def test_reduce_numeric_collection_uses_item():
    src = '''let numbers = [1, 2, 3, 4, 5]
total = numbers reduce 0 with acc + item
show total
'''
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["total"] == 15


def test_reduce_record_collection_accepts_bare_field_shorthand():
    src = """data numbers:
    a value 1
    b value 2
    c value 3

total = numbers reduce 0 with acc + value
show total
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["total"] == 6
    expr = p.ast.reduces[0].expr
    assert expr.right.base.name == "row"
    assert expr.right.name == "value"


def test_reduce_record_collection_accepts_explicit_row_and_item_fields():
    for current in ("row.value", "item.value"):
        src = f"""data numbers:
    a value 1
    b value 2

total = numbers reduce 0 with acc + {current}
show total
"""
        p = parse(src)
        validate(p)
        run(p)
        assert p._collections["total"] == 3


def test_reduce_numeric_collection_rejects_record_field_shorthand():
    p = parse("""let numbers = [1, 2, 3]
total = numbers reduce 0 with acc + value
""")
    try:
        validate(p)
    except TypeError as exc:
        assert "unknown field 'value' on Number" in str(exc)
        return
    assert False, "bare field shorthand must not be accepted for scalar items"


def test_reduce_is_a_general_typed_fold():
    src = """data numbers:
    a value 1
    b value 2
    c value 3
    d value 4

product = numbers reduce 1 with acc * value
show product
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["product"] == 24
    assert isinstance(p.ast.reduces[0], ReduceOp)
    assert show_expr_value(p, p.ast.shows[0].target) == "24"


def test_reduce_can_follow_map_and_use_scalar_item():
    src = """data numbers:
    a value 1
    b value 2
    c value 3

values = numbers map value * 10
total = values reduce 0 with acc + item
show total
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["total"] == 60


def test_reduce_empty_collection_returns_initial_value():
    src = """data numbers:
    a value 1
    b value 2

empty = numbers where value > 100
result = empty reduce 42 with acc + value
show result
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["result"] == 42


def test_reduce_step_type_must_match_accumulator():
    p = parse("""data numbers:
    a value 1
    b value 2

bad = numbers reduce 0 with acc + value * 1 m
""")
    try:
        validate(p)
    except TypeError as e:
        assert "reduce step returns" in str(e) or "cannot add" in str(e)
        return
    assert False


def test_text_reduce_is_string_concatenation():
    src = '''let labels = ["Ada", "Eve", "Lin"]
joined = labels reduce "" with acc + item
show joined
'''
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["joined"] == "AdaEveLin"


def test_text_subtraction_remains_invalid():
    src = '''let labels = ["Ada"]
bad = labels reduce "" with acc - item
'''
    p = parse(src)
    try:
        validate(p)
    except TypeError as e:
        assert "cannot subtract Text and Text" in str(e) or "reduce step returns" in str(e)
        return
    assert False
