# S-Lang 1.12.82: scan_values_right
values = [1, 2, 3, 4]
partial_suffix_sums = scan_values_right(values, 0, (total, value) -> total + value)
# partial_suffix_sums = [10, 9, 7, 4]
