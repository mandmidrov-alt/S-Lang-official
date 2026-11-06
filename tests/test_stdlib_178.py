from slang.core import parse, run, show_expr_value, validate, parse_expr
from slang.semantic import TypeEnv, infer
from slang.types import BOOLEAN, NUMBER, RECORD, list_type


def test_analytics_signatures():
    env = TypeEnv({}, {}, {})
    assert infer(parse_expr('window([{id: 1}], 1, 1)'), env) == list_type(list_type(RECORD))
    assert infer(parse_expr('rank_by([{id: 1}], "id", false)'), env) == list_type(RECORD)
    assert infer(parse_expr('top_by([{id: 1}], "id", 1)'), env) == list_type(RECORD)
    assert infer(parse_expr('bottom_by([{id: 1}], "id", 1)'), env) == list_type(RECORD)


def test_analytics_runtime():
    source = '''let rows = [{id: 1, score: 30}, {id: 2, score: 10}, {id: 3, score: 30}, {id: 4, score: 20}]
let windows = window(rows, 2, 1)
let ranked = rank_by(rows, "score", true)
let top = top_by(rows, "score", 2)
let bottom = bottom_by(rows, "score", 2)
show windows
show ranked
show top
show bottom
'''
    p = parse(source)
    validate(p)
    run(p)
    assert [show_expr_value(p, e) for e in p.show_exprs] == [
        "[[{'id': 1, 'score': 30}, {'id': 2, 'score': 10}], [{'id': 2, 'score': 10}, {'id': 3, 'score': 30}], [{'id': 3, 'score': 30}, {'id': 4, 'score': 20}]]",
        '[row(id=1, score=30, rank=1), row(id=2, score=10, rank=4), row(id=3, score=30, rank=1), row(id=4, score=20, rank=3)]',
        '[row(id=1, score=30), row(id=3, score=30)]',
        '[row(id=2, score=10), row(id=4, score=20)]',
    ]
