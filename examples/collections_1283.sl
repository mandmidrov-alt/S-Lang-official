# S-Lang 1.12.83 — running_values
values = [1, 2, 3, 4]

# Use the first value as the initial state and return every intermediate result.
totals = running_values(values, (total, value) -> total + value)

# totals = [1, 3, 6, 10]
