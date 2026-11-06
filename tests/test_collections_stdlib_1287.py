from slang.stdlib import aggregate_groups
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_aggregate_groups():
    values = [1, 2, 3, 4, 5]
    assert aggregate_groups(values, lambda x: x % 2, lambda group: sum(group)) == {1: 9, 0: 6}


def test_aggregate_groups_preserves_key_order():
    values = [10, 11, 12, 13]
    result = aggregate_groups(values, lambda x: x % 3, len)
    assert list(result.keys()) == [1, 2, 0]


def test_aggregate_groups_does_not_mutate_input():
    values = [1, 2, 3]
    original = values[:]
    aggregate_groups(values, lambda x: x % 2, lambda group: list(reversed(group)))
    assert values == original


def test_aggregate_groups_validation():
    try:
        aggregate_groups([1], None, sum)
        assert False
    except TypeError:
        pass
    try:
        aggregate_groups([1], lambda x: x, None)
        assert False
    except TypeError:
        pass


def test_aggregate_groups_public_api():
    assert get("aggregate_groups") is not None
    assert "aggregate_groups" in signatures()
    assert any(entry["name"] == "aggregate_groups" for entry in entries())
