from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import ANY, RECORD, TEXT, list_type


def test_relational_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('distinct_by([{id: 1}], "id")'), env) == list_type(RECORD)
    assert infer(parse_expr('join_records([{id: 1}], [{id: 1}], "id", "id")'), env) == list_type(RECORD)
    assert infer(parse_expr('partition([{id: 1}], "id", 1)'), env) == RECORD


def test_distinct_join_partition_runtime():
    source = '''let left = [{id: 1, name: "A"}, {id: 1, name: "A2"}, {id: 2, name: "B"}]
let right = [{id: 1, score: 10}, {id: 2, score: 20}, {id: 3, score: 30}]
let unique = distinct_by(left, "id")
let joined = join_records(left, right, "id", "id")
let parts = partition(left, "id", 1)
show unique
show joined
show parts
'''
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == "[A(id=1), B(id=2)]"
    assert show_expr_value(p, p.show_exprs[1]) == "[A(id=1, score=10), A2(id=1, score=10), B(id=2, score=20)]"
    assert show_expr_value(p, p.show_exprs[2]) == "{'matching': [{'id': 1, 'name': 'A'}, {'id': 1, 'name': 'A2'}], 'rest': [{'id': 2, 'name': 'B'}]}"


def test_relational_empty_inputs():
    source = '''let rows = []
let unique = distinct_by(rows, "id")
let joined = join_records(rows, rows, "id", "id")
let parts = partition(rows, "id", 1)
show unique
show joined
show parts
'''
    p = parse(source)
    validate(p)
    run(p)
    assert [show_expr_value(p, expr) for expr in p.show_exprs] == [
        '[]', '[]', "{'matching': [], 'rest': []}"
    ]
