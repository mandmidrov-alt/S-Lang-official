# Direct grouping + aggregation
values = [1, 2, 3, 4, 5]
result = aggregate_values_by(values, key = (x) => x % 2, aggregate = sum)
