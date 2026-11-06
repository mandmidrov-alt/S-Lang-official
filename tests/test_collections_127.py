from slang.stdlib.collections import product_numbers, average_number, median_number


def test_product_average_median():
    assert product_numbers([2, 3, 4]) == 24
    assert product_numbers([]) == 1
    assert average_number([1, 2, 4]) == 7 / 3
    assert median_number([1, 9, 3]) == 3
    assert median_number([1, 2, 10, 20]) == 6


def test_numeric_collection_validation():
    for fn in (product_numbers, average_number, median_number):
        try:
            fn([1, True])
        except TypeError:
            pass
        else:
            raise AssertionError(f"{fn.__name__} accepted Boolean")
    for fn in (average_number, median_number):
        try:
            fn([])
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"{fn.__name__} accepted empty list")
