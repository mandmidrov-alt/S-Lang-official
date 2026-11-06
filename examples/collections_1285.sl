# Partition values by a computed key.
values = ["ant", "apple", "bee", "avocado"]
partitions = partition_by_values(values, key = value -> value[0])
