# Fold a collection into one result.
# Expected result: 10

fold_values([1, 2, 3, 4], 0, (total, value) -> total + value)
