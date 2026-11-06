# Predicate-based prefix selection in S-Lang 1.12.31

values = [2, 4, 6, 8, 9, 10]

leading_even = take_while(values, x -> x % 2 == 0)
