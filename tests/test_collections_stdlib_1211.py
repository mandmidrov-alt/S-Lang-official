from slang.stdlib.collections import cumulative_sum_numbers, cumulative_product_numbers

def test_cumulative_sum_numbers():
    assert cumulative_sum_numbers([1,2,3]) == [1,3,6]
    assert cumulative_sum_numbers([]) == []

def test_cumulative_product_numbers():
    assert cumulative_product_numbers([2,3,4]) == [2,6,24]
    assert cumulative_product_numbers([]) == []
