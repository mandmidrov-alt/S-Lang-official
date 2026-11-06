from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import RECORD, TEXT, list_type


def test_aggregation_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('group_by([{team: "A"}], "team")'), env) == list_type(RECORD)
    assert infer(parse_expr('group_count([{team: "A"}], "team")'), env) == list_type(RECORD)
    assert infer(parse_expr('group_sum([{team: "A", score: 2}], "team", "score")'), env) == list_type(RECORD)
    assert infer(parse_expr('group_average([{team: "A", score: 2}], "team", "score")'), env) == list_type(RECORD)
    assert infer(parse_expr('group_min([{team: "A", score: 2}], "team", "score")'), env) == list_type(RECORD)
    assert infer(parse_expr('group_max([{team: "A", score: 2}], "team", "score")'), env) == list_type(RECORD)


def test_aggregation_runtime():
    source = '''let people = [{team: "A", score: 10}, {team: "B", score: 5}, {team: "A", score: 20}, {team: "B", score: 15}, {team: "A", score: 30}]
let groups = group_by(people, "team")
let counts = group_count(people, "team")
let sums = group_sum(people, "team", "score")
let averages = group_average(people, "team", "score")
show groups
show counts
show sums
show averages
'''
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "[row(key=A, items=[{'team': 'A', 'score': 10}, {'team': 'A', 'score': 20}, {'team': 'A', 'score': 30}]), row(key=B, items=[{'team': 'B', 'score': 5}, {'team': 'B', 'score': 15}])]"
    assert show_expr_value(p, p.show_exprs[1]) == "[row(key=A, count=3), row(key=B, count=2)]"
    assert show_expr_value(p, p.show_exprs[2]) == "[row(key=A, sum=60), row(key=B, sum=20)]"
    assert show_expr_value(p, p.show_exprs[3]) == "[row(key=A, average=20.0), row(key=B, average=10.0)]"


def test_empty_aggregation():
    source = 'let rows = []\nlet result = group_count(rows, "team")\nshow result\n'
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '[]'
