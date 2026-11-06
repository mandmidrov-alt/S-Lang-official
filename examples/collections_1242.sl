# S-Lang 1.12.42: indexed collection transformation

values = [10, 20, 30]

indexed = map_with_index(values, (value, index) -> value + index)
labels = map_with_index(values, (value, index) -> index + ":" + value)
