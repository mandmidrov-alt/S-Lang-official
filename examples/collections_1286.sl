# S-Lang 1.12.86: group projected values by key

values = ["ant", "apple", "bee", "avocado"]
groups = group_values_by(values, fn(x) => x[0], fn(x) => length(x))

# groups => {"a": [3, 5, 7], "b": [3]}
