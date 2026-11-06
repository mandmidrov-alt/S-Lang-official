from slang.core import parse, validate, run


def test_where_implicit_item():
    p = parse("""let values = [1, 2, 3]
result = values |> where >= 2
show result
""")
    validate(p); run(p)
    assert p._collections["result"] == [2, 3]


def test_map_implicit_item():
    p = parse("""let values = [1, 2, 3]
result = values |> map * 10
show result
""")
    validate(p); run(p)
    assert p._collections["result"] == [10, 20, 30]


def test_dot_field_implicit_item():
    p = parse("""data people:
    a score 3
    b score 1
    c score 2
result = people |> sort by .score asc
show result
""")
    validate(p); run(p)
    assert [x["name"] for x in p._collections["result"]] == ['b', 'c', 'a']


def test_conditional_branch_uses_implicit_item():
    p = parse("""let values = [1, 2, 3]
let enabled = true
result = values |> if enabled then (where >= 2 |> map * 10) else (where >= 3 |> map * 2)
show result
""")
    validate(p); run(p)
    assert p._collections["result"] == [20, 30]


def test_aggregate_implicit_item():
    p = parse("""let values = [1, 2, 3]
result = values |> sum
show result
""")
    validate(p); run(p)
    assert p._collections["result"] == 6
