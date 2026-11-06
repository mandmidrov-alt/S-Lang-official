# Predicate-based suffix selection in S-Lang 1.12.32

values = [1, 2, 3, 4, 5]

remaining = drop_while(values, x -> x < 3)
all_remaining = drop_while(values, x -> x < 10)
unchanged = drop_while(values, x -> x < 0)
