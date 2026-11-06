from slang.core import parse, validate, run, show_expr_value


def test_goal_directed_transition_can_filter_candidates_with_satisfy():
    source = """\nmodule test\nsequence path from 1 for up to 8 steps toward 20 choosing:\n    value + 1\n    value + 3\n    value * 2\n    satisfy candidate <= 20\nshow path\n"""
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "[1, 4, 8, 16, 19, 20]"


def test_goal_directed_transition_rejects_non_boolean_constraint():
    source = """\nmodule test\nsequence path from 1 for up to 3 steps toward 10 choosing:\n    value + 1\n    value + 2\n    satisfy candidate + 1\n"""
    p = parse(source)
    try:
        validate(p)
    except TypeError as exc:
        assert "satisfy constraint must be Boolean" in str(exc)
    else:
        raise AssertionError("expected Boolean constraint validation failure")


def test_goal_directed_transition_supports_composite_constraint_and_external_state():
    source = """\nmodule test\nlet lower_limit = 2\nlet upper_limit = 20\nsequence path from 1 for up to 8 steps toward 18 choosing:\n    value + 1\n    value + 3\n    value * 2\n    satisfy (candidate >= lower_limit and candidate <= upper_limit) and not (candidate == value)\nshow path\n"""
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "[1, 4, 8, 16, 17, 18, 19, 20]"
