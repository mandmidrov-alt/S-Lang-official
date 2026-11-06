# Predicate-based collection partitioning in S-Lang 1.12.29

values = [1, 2, 3, 4, 5]

parts = partition_values(values, x -> x % 2 == 0)
even_values = parts[0]
odd_values = parts[1]
