"""Actionable error messages for common collection-operation mistakes."""
import pytest

from slang.stdlib.collections import (
    count_by_values,
    distinct_by_values,
    group_by_values,
    index_by_values,
    sort_by_values,
    sort_descending_values,
    sort_values,
)


@pytest.mark.parametrize("sorter", [sort_values, sort_descending_values])
def test_sort_reports_incomparable_items_with_recovery_hint(sorter):
    with pytest.raises(TypeError, match="cannot compare every item") as exc:
        sorter([1, "two"])
    assert "sort_by_values" in str(exc.value)


def test_sort_by_reports_incompatible_computed_keys():
    with pytest.raises(TypeError, match="computed sort keys"):
        sort_by_values([1, "two"], lambda value: value)


@pytest.mark.parametrize(
    ("operation", "name"),
    [
        (lambda: group_by_values([[1], [2]], lambda value: value), "group_by_values"),
        (lambda: count_by_values([[1], [2]], lambda value: value), "count_by_values"),
        (lambda: index_by_values([[1], [2]], lambda value: value), "index_by_values"),
        (lambda: distinct_by_values([[1], [2]], lambda value: value), "distinct_by_values"),
    ],
)
def test_keyed_collection_operations_explain_unhashable_keys(operation, name):
    with pytest.raises(TypeError, match="unhashable key") as exc:
        operation()
    assert name in str(exc.value)
    assert "Text, Number, or Boolean" in str(exc.value)


def test_index_by_duplicate_key_suggests_unique_identifier():
    with pytest.raises(ValueError, match="unique computed keys") as exc:
        index_by_values([{"id": 1}, {"id": 1}], lambda item: item["id"])
    assert "uniquely identifies" in str(exc.value)


def test_collection_diagnostics_do_not_change_valid_results():
    assert sort_values([3, 1, 2]) == [1, 2, 3]
    assert group_by_values([1, 2, 3], lambda value: value % 2) == {1: [1, 3], 0: [2]}
    assert count_by_values(["a", "b", "a"], lambda value: value) == {"a": 2, "b": 1}
