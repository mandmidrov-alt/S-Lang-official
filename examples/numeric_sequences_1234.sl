# Predicate-based collection suffix selection in S-Lang 1.12.34

values = [1, 2, 3, 4, 5]

from_three = drop_until(values, x -> x >= 3)
missing = drop_until(values, x -> x > 9)
