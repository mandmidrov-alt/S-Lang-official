from slang.core import parse, run, validate, show_expr_value, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import ANY, BOOLEAN, NUMBER, RECORD, TEXT, list_type


def test_task_level_record_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('order_by([{id: 1}], "id", false)'), env) == list_type(RECORD)
    assert infer(parse_expr('find_by([{id: 1}], "id", 1)'), env) == ANY
    assert infer(parse_expr('count_by([{id: 1}], "id", 1)'), env) == NUMBER


def test_task_level_record_runtime():
    source = '''let rows = [{id: 1, score: 20}, {id: 2, score: 10}, {id: 3, score: 20}]
let ordered = order_by(rows, "score", false)
let descending = order_by(rows, "score", true)
let found = find_by(rows, "id", 2)
let missing = find_by(rows, "id", 9)
let count = count_by(rows, "score", 20)
show ordered
show descending
show found
show missing
show count
'''
    p = parse(source)
    validate(p)
    run(p)
    assert [show_expr_value(p, expr) for expr in p.show_exprs] == [
        '[row(id=2, score=10), row(id=1, score=20), row(id=3, score=20)]',
        '[row(id=1, score=20), row(id=3, score=20), row(id=2, score=10)]',
        "{'id': 2, 'score': 10}",
        'None',
        '2',
    ]


def test_order_by_is_stable_for_equal_keys():
    source = '''let rows = [{id: 1, score: 10}, {id: 2, score: 10}, {id: 3, score: 5}]
let ordered = order_by(rows, "score", false)
show ordered
'''
    p = parse(source)
    validate(p)
    run(p)
    assert show_expr_value(p, p.show_exprs[0]) == '[row(id=3, score=5), row(id=1, score=10), row(id=2, score=10)]'
