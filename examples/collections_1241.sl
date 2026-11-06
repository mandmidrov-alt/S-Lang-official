# Declarative collection mapping in S-Lang 1.12.41

values = [1, 2, 3, 4]
doubled = map_values(values, x -> x * 2)
labels = map_values(values, x -> "item:" + text(x))
