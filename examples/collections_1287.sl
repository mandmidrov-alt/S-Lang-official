# Declarative aggregation of groups
# aggregate_groups groups values by a computed key and reduces each group to one result.

numbers = [1, 2, 3, 4, 5, 6]
result = aggregate_groups(numbers, fn x: x % 2, fn group: sum(group))
print(result)
