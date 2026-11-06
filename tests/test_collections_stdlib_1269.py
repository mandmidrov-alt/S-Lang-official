from slang.stdlib import reverse_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_reverse_values_reverses_order():
    assert reverse_values([1, 2, 3, 4]) == [4, 3, 2, 1]


def test_reverse_values_handles_empty_and_singleton():
    assert reverse_values([]) == []
    assert reverse_values([1]) == [1]


def test_reverse_values_does_not_mutate_input():
    values = [1, 2, 3]
    result = reverse_values(values)
    assert values == [1, 2, 3]
    assert result is not values


def test_reverse_values_public_api():
    assert get("reverse_values") is not None
    assert "reverse_values" in signatures()
    assert any(e["name"] == "reverse_values" for e in entries())
