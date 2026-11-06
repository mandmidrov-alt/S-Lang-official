from slang.core import parse, run, show_expr_value, validate, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import RECORD, list_type


def test_analytics_179_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('window_sum([{id: 1, score: 10}], "score", 1, 1)'), env) == list_type(RECORD)
    assert infer(parse_expr('window_average([{id: 1, score: 10}], "score", 1, 1)'), env) == list_type(RECORD)
    assert infer(parse_expr('group_top_by([{team: "A", score: 10}], "team", "score", 1)'), env) == list_type(RECORD)


def test_analytics_179_runtime():
    source = '''let rows = [{team: "A", score: 30}, {team: "B", score: 10}, {team: "A", score: 20}, {team: "B", score: 40}]
let sums = window_sum(rows, "score", 2, 1)
let averages = window_average(rows, "score", 2, 1)
let tops = group_top_by(rows, "team", "score", 1)
show sums
show averages
show tops
'''
    p = parse(source)
    validate(p)
    run(p)
    assert [show_expr_value(p, e) for e in p.show_exprs] == [
        "[row(start=0, sum=40), row(start=1, sum=30), row(start=2, sum=60)]",
        "[row(start=0, average=20.0), row(start=1, average=15.0), row(start=2, average=30.0)]",
        "[row(team=A, score=30), row(team=B, score=40)]",
    ]
