from slang.stdlib.math import normalize_number, remap_number
from slang.stdlib.registry import REGISTRY


def test_normalize_and_remap():
    assert normalize_number(5, 0, 10) == 0.5
    assert normalize_number(0, 0, 10) == 0
    assert normalize_number(10, 0, 10) == 1
    assert remap_number(5, 0, 10, 100, 200) == 150
    assert remap_number(0, 0, 10, 10, 20) == 10
    assert remap_number(10, 0, 10, 10, 20) == 20


def test_validation_and_registry():
    for fn, args in [
        (normalize_number, (1, 2, 2)),
        (remap_number, (1, 2, 2, 0, 1)),
    ]:
        try:
            fn(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")
    assert "normalize_number" in REGISTRY
    assert "remap_number" in REGISTRY
