from slang.core import parse, validate, run, show_expr_value

def test_multiple_structured_satisfy_constraints_are_conjoined():
    source = """
module test
entity Point:
    x: Number
    y: Number
let lower = 0
let upper = 4
sequence path from Point(0, 0) for up to 4 steps toward Point(4, 4) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 2)
    Point(value.x + 3, value.y + 3)
    satisfy candidate.x >= lower
    satisfy candidate.y >= lower
    satisfy candidate.x <= upper and candidate.y <= upper
    satisfy not (candidate.x == value.x and candidate.y == value.y)
show path
"""
    p = parse(source); validate(p); run(p)
    assert "x': 4" in show_expr_value(p, p.show_exprs[0])

def test_multiple_satisfy_constraints_reject_non_boolean():
    source = """
module test
entity Point:
    x: Number
    y: Number
sequence path from Point(0, 0) for up to 2 steps toward Point(2, 2) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 1)
    satisfy candidate.x > 0
    satisfy 1
"""
    p = parse(source)
    try:
        validate(p)
    except TypeError as exc:
        assert "satisfy constraint must be Boolean" in str(exc)
    else:
        raise AssertionError("expected Boolean constraint validation failure")
