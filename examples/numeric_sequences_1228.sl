# Predicate-based counting in S-Lang 1.12.28

values = [1, 2, 3, 4, 5, 6]

even_count = count_if(values, x -> x % 2 == 0)
large_count = count_if(values, x -> x > 3)
