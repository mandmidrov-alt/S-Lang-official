import pytest

from slang.core import ParseError, parse, validate


def test_function_single_return_is_valid():
    p = parse('''
function double(x: Number) -> Number:
    return x * 2
''')
    validate(p)


def test_function_if_else_both_return_is_valid():
    p = parse('''
function classify(x: Number) -> Text:
    if x > 0:
        return "positive"
    else:
        return "nonpositive"
''')
    validate(p)


def test_function_one_branch_return_is_rejected():
    with pytest.raises(ParseError, match='all control-flow paths'):
        parse('''
function classify(x: Number) -> Text:
    if x > 0:
        return "positive"
''')


def test_function_can_return_after_partial_if():
    p = parse('''
function classify(x: Number) -> Text:
    if x > 0:
        let y = x
    return "done"
''')
    validate(p)


def test_property_requires_total_return():
    with pytest.raises(ParseError, match='all control-flow paths'):
        parse('''
property Body.mass -> Number:
    if true:
        return 1
''')
