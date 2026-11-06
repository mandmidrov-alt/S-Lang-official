# S-Lang 1.12.89: aggregate_values_by_with_key
# Aggregate each group while retaining its computed key.

values = [1, 2, 3, 4, 5]
result = aggregate_values_by_with_key(
    values,
    (value) => value % 2,
    (group_key, group) => [group_key, sum(group)]
)
