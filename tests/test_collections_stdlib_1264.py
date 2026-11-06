from slang.stdlib import has_exactly_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_exact_size_matches():
    assert has_exactly_values([1, 2, 3], 3) is True
    assert has_exactly_values([1, 2, 3], 2) is False


def test_empty_exact_size():
    assert has_exactly_values([], 0) is True
    assert has_exactly_values([], 1) is False


def test_negative_and_invalid_counts():
    import pytest
    with pytest.raises(ValueError):
        has_exactly_values([1], -1)
    with pytest.raises(TypeError):
        has_exactly_values([1], True)


def test_no_mutation():
    values = [1, 2]
    has_exactly_values(values, 2)
    assert values == [1, 2]


def test_public_api_registry_and_catalog():
    assert get('has_exactly_values') is not None
    assert 'has_exactly_values' in signatures()
    assert any(e['name'] == 'has_exactly_values' for e in entries())
