from slang.stdlib import take_every_values
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_take_every_values():
    assert take_every_values([0, 1, 2, 3, 4, 5], 2) == [0, 2, 4]
    assert take_every_values([0, 1, 2, 3, 4, 5], 3) == [0, 3]


def test_step_one_and_large_step():
    assert take_every_values([1, 2, 3], 1) == [1, 2, 3]
    assert take_every_values([1, 2, 3], 10) == [1]
    assert take_every_values([], 2) == []


def test_invalid_step():
    import pytest
    with pytest.raises(ValueError):
        take_every_values([1], 0)
    with pytest.raises(ValueError):
        take_every_values([1], -1)
    with pytest.raises(TypeError):
        take_every_values([1], True)


def test_no_mutation():
    values = [1, 2, 3, 4]
    assert take_every_values(values, 2) == [1, 3]
    assert values == [1, 2, 3, 4]


def test_public_api_registry_and_catalog():
    assert get('take_every_values') is not None
    assert 'take_every_values' in signatures()
    assert any(e['name'] == 'take_every_values' for e in entries())
