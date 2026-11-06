from slang.stdlib import count_by_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_count_by_values_counts_by_key():
    result = count_by_values(["apple", "apricot", "banana", "blueberry"], lambda value: value[0])
    assert result == {"a": 2, "b": 2}


def test_count_by_values_preserves_key_order_and_does_not_mutate():
    values = [1, 2, 3, 4, 5]
    result = count_by_values(values, lambda value: value % 2)
    assert list(result.keys()) == [1, 0]
    assert result == {1: 3, 0: 2}
    assert values == [1, 2, 3, 4, 5]


def test_count_by_values_rejects_non_callable_key():
    try:
        count_by_values([1, 2], "parity")
    except TypeError as exc:
        assert str(exc) == "count_by_values expects a callable key"
    else:
        raise AssertionError("expected TypeError")


def test_count_by_values_public_api():
    assert get("count_by_values") is not None
    assert "count_by_values" in signatures()
    assert any(item["name"] == "count_by_values" for item in entries())
