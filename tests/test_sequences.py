import pytest
from slang.core import parse, run, validate, show_expr_value
from slang.ast import SequenceOp


def test_sequence_generates_state_values():
    p = parse("sequence values from 1 for 5 steps using value * 3 + 1\nshow values")
    validate(p)
    run(p)
    assert p._collections["values"] == [1, 4, 13, 40, 121]


def test_sequence_can_feed_map():
    p = parse("sequence values from 1 for 4 steps using value * 2\ndoubled = values map item + 1")
    validate(p)
    run(p)
    assert p._collections["doubled"] == [2, 3, 5, 9]


def test_sequence_type_is_preserved():
    p = parse("sequence values from 1 for 3 steps using value * 2\nshow values")
    validate(p)
    assert str(p.ast.sequences[0].result) == "values"


def test_sequence_rejects_incompatible_transition():
    p = parse("sequence values from 1 for 3 steps using value > 0")
    with pytest.raises(TypeError, match="sequence 'values' step returns"):
        validate(p)


def test_sequence_rejects_zero_steps():
    with pytest.raises(Exception, match="steps must be positive"):
        parse("sequence values from 1 for 0 steps using value + 1")
