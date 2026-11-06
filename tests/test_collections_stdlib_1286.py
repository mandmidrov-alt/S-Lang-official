from slang.stdlib import group_values_by
from slang.stdlib.registry import get, signatures
from slang.stdlib.catalog import entries


def test_group_values_by_projects_values():
    values = ["ant", "apple", "bee", "avocado"]
    assert group_values_by(values, lambda x: x[0], len) == {"a": [3, 5, 7], "b": [3]}


def test_group_values_by_preserves_order_and_input():
    values = ["ax", "by", "az", "bx"]
    assert group_values_by(values, lambda x: x[0], lambda x: x[1]) == {"a": ["x", "z"], "b": ["y", "x"]}
    assert values == ["ax", "by", "az", "bx"]


def test_group_values_by_validates_callables():
    try:
        group_values_by([1], None, lambda x: x)
    except TypeError as exc:
        assert "callable key" in str(exc)
    else:
        raise AssertionError("expected TypeError")

    try:
        group_values_by([1], lambda x: x, None)
    except TypeError as exc:
        assert "callable value" in str(exc)
    else:
        raise AssertionError("expected TypeError")


def test_group_values_by_public_api():
    assert get("group_values_by") is not None
    assert "group_values_by" in signatures()
    assert any(entry["name"] == "group_values_by" for entry in entries())
