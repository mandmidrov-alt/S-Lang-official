from slang.core import parse, validate, run, show_expr_value


def test_structured_goal_satisfy_uses_candidate_fields():
    source = """
module test
entity Point:
    x: Number
    y: Number
let upper = 10
sequence path from Point(0, 0) for up to 8 steps toward Point(10, 10) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 2)
    satisfy (candidate.x <= upper and candidate.y <= upper) and not (candidate.x == value.x and candidate.y == value.y)
show path
"""
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "[UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 0}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 2}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 4}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 6}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 8}), UserEntity(type_name='Point', name='Point_value', fields={'x': 0, 'y': 10}), UserEntity(type_name='Point', name='Point_value', fields={'x': 1, 'y': 10}), UserEntity(type_name='Point', name='Point_value', fields={'x': 2, 'y': 10})]"


def test_structured_goal_satisfy_rejects_unknown_candidate_field():
    source = """
module test
entity Point:
    x: Number
    y: Number
sequence path from Point(0, 0) for up to 2 steps toward Point(2, 2) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 1)
    satisfy candidate.z > 0
"""
    p = parse(source)
    try:
        validate(p)
    except TypeError as exc:
        assert "unknown field 'z'" in str(exc)
    else:
        raise AssertionError("expected structured candidate field validation failure")
