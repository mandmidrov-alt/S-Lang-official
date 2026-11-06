from slang.stdlib import sort_by_values

def test_sort_by_values_uses_key():
    values = ["bbb", "a", "cc"]
    assert sort_by_values(values, len) == ["a", "cc", "bbb"]

def test_sort_by_values_is_stable():
    values = [("a", 1), ("b", 1), ("c", 2)]
    assert sort_by_values(values, lambda item: item[1]) == values

def test_sort_by_values_does_not_mutate():
    values = [3, 1, 2]
    original = list(values)
    assert sort_by_values(values, lambda value: value) == [1, 2, 3]
    assert values == original
