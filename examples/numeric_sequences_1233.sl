# Predicate-based prefix selection in S-Lang 1.12.33

values = [1, 2, 3, 4, 5]

before_three = take_until(values, x -> x == 3)
before_large = take_until(values, x -> x > 3)
