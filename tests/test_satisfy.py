from slang.core import parse, validate, run


def test_satisfy_finds_deterministic_solution():
    p = parse('''
solution = satisfy:
    x in 1..10
    y in 1..10
    x + y == 12
    x < y
show solution
''')
    run(p)
    assert p._collections['solution'] == {'x': 2, 'y': 10}


def test_satisfy_uses_declaration_order_for_lexicographic_selection():
    p = parse('''
solution = satisfy:
    x in 1..3
    y in 1..3
    x + y == 4
show solution
''')
    run(p)
    assert p._collections['solution'] == {'x': 1, 'y': 3}


def test_satisfy_rejects_non_boolean_constraint():
    p = parse('''
solution = satisfy:
    x in 1..3
    x + 1
''')
    try:
        validate(p)
    except TypeError as exc:
        assert 'Boolean' in str(exc)
    else:
        raise AssertionError('expected TypeError')


def test_satisfy_reports_unsatisfiable_problem():
    p = parse('''
solution = satisfy:
    x in 1..3
    x > 10
''')
    try:
        run(p)
    except TypeError as exc:
        assert "found no solution" in str(exc)
    else:
        raise AssertionError('expected TypeError')


def test_satisfy_uses_constraint_propagation_for_large_bounded_domains():
    p = parse('''
solution = satisfy:
    x in 1..100000
    y in 1..100000
    x + y == 199999
    x < y
show solution
''')
    run(p)
    assert p._collections['solution'] == {'x': 99999, 'y': 100000}


def test_satisfy_constraint_propagation_keeps_final_semantics_for_non_linear_constraints():
    p = parse('''
solution = satisfy:
    x in 1..6
    y in 1..6
    x * y == 12
    x < y
show solution
''')
    run(p)
    assert p._collections['solution'] == {'x': 2, 'y': 6}


def test_constraint_propagation_preserves_strict_inequality_solution():
    p = parse('''
solution = satisfy:
    x in 1..100
    y in 1..100
    x + y == 31
    x < y
''')
    run(p)
    assert p._collections["solution"] == {"x": 1, "y": 30}
