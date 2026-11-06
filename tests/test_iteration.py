import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run, show_expr_value
from slang.ast import MapOp, AggregateOp


def test_map_is_a_generic_collection_operation():
    src = """data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

scores = students map score * 2
show scores
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["scores"] == [182, 176, 190]
    assert isinstance(p.ast.maps[0], MapOp)
    assert show_expr_value(p, p.ast.shows[0].target) == "[182, 176, 190]"


def test_aggregates_are_generic():
    src = """data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

total = students sum score
average = students average score
count = students count
show total
show average
show count
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["total"] == 274
    assert p._collections["average"] == 274 / 3
    assert p._collections["count"] == 3
    assert len(p.ast.aggregates) == 3
    assert all(isinstance(x, AggregateOp) for x in p.ast.aggregates)


def test_map_can_follow_filter_and_use_function():
    src = """function adjusted(x: Number) -> Number:
    return x + 10

data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

adults = students where age >= 18
values = adults map adjusted(score)
show values
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["values"] == [101, 105]


def test_unknown_map_source_is_rejected():
    p = parse("values = missing map score * 2")
    try:
        validate(p)
    except TypeError as e:
        assert "unknown collection 'missing'" in str(e)
        return
    assert False


def test_aggregate_requires_numeric_expression():
    p = parse("""data people:
    Alice name_x x

total = people sum name_x
""")
    try:
        validate(p)
    except TypeError as e:
        assert "requires a numeric expression" in str(e)
        return
    assert False


def test_collection_pipeline_is_order_independent_by_dependency():
    src = """data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

adults = students where age >= 18
values = adults map score * 2
show values
"""
    p = parse(src)
    validate(p)
    run(p)
    assert p._collections["values"] == [182, 190]
