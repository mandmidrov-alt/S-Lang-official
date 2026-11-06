from slang.stdlib.collections import span_while


def test_span_while_splits_prefix_and_suffix():
    assert span_while([1, 2, 3, 4], lambda x: x < 3) == [[1, 2], [3, 4]]


def test_span_while_all_and_none_match():
    assert span_while([1, 2], lambda x: x > 0) == [[1, 2], []]
    assert span_while([1, 2], lambda x: x > 9) == [[], [1, 2]]


def test_span_while_empty_and_invalid_predicate():
    assert span_while([], lambda x: True) == [[], []]
    import pytest
    with pytest.raises(TypeError):
        span_while([1], 2)
