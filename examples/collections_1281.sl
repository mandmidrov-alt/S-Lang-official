# S-Lang 1.12.81: scan_values
values = [1, 2, 3, 4]
partial_sums = scan_values(values, 0, (total, value) -> total + value)
# partial_sums = [1, 3, 6, 10]
