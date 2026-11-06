import sys
sys.path.insert(0, '.')
from slang.core import parse, validate, run
from slang.types import NUMBER, list_type, Type


def test_map_infers_element_type():
    p = parse('''data students:\n    Alice age 22 score 91\n    Bob age 17 score 88\n\nscores = students map score * 2\n''')
    validate(p)
    assert p.ast is not None
    # Collection aliases are exposed through the semantic environment by validation.
    # Re-validate indirectly by checking the runtime pipeline result type shape.
    run(p)
    assert p._collections['scores'] == [182, 176]


def test_scalar_collection_pipeline_uses_item():
    p = parse('''data students:\n    Alice age 22 score 91\n    Bob age 17 score 88\n\nscores = students map score\ndoubled = scores map item * 2\n''')
    validate(p)
    run(p)
    assert p._collections['scores'] == [91, 88]
    assert p._collections['doubled'] == [182, 176]


def test_filter_preserves_row_element_type_and_chain_works():
    p = parse('''data students:\n    Alice age 22 score 91\n    Bob age 17 score 88\n    Carol age 31 score 95\n\nadults = students where age >= 18\nvalues = adults map score\ntop = values where item >= 92\n''')
    validate(p)
    run(p)
    assert p._collections['values'] == [91, 95]
    assert p._collections['top'] == [95]


def test_bad_scalar_filter_is_rejected():
    p = parse('''data students:\n    Alice age 22 score 91\n\nscores = students map score\nbad = scores where item + 1\n''')
    try:
        validate(p)
    except TypeError as e:
        assert 'where condition must be Boolean' in str(e)
        return
    assert False


def test_map_expression_type_error_is_rejected():
    p = parse('''data students:\n    Alice age 22 score 91\n\nbad = students map score + 2 kg\n''')
    try:
        validate(p)
    except TypeError as e:
        assert 'cannot add' in str(e)
        return
    assert False
