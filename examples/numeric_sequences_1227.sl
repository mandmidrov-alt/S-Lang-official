# Predicate-based index selection in S-Lang 1.12.27

values = [10, 15, 20, 25, 30]

matching_indices = find_all_indices(values, x -> x >= 20)
