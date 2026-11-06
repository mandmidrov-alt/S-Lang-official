# Predicate-based prefix/suffix splitting in S-Lang 1.12.35

values = [1, 2, 3, 4, 5]

parts = span_while(values, x -> x < 3)
matching = parts[0]
remaining = parts[1]
