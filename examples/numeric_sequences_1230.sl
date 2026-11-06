# Predicate-based index partitioning in S-Lang 1.12.30

values = [10, 3, 8, 1, 6]

indices = partition_indices(values, x -> x >= 6)
