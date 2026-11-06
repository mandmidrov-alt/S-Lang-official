# Predicate-based collection filtering in S-Lang 1.12.26

values = [1, 2, 3, 4, 5]

even_values = find_all(values, x -> x % 2 == 0)
large_values = find_all(values, x -> x > 3)
