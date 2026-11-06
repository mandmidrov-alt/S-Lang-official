sales = [
    ("A", 10, 3, 1), ("B", 7, 5, 2), ("C", 20, 2, 1),
    ("D", 4, 10, 3), ("E", 12, 1, 1)
]
regional = sorted([r for r in sales if r[3] == 1], key=lambda r: r[1], reverse=True)
values = [r[1] * r[2] for r in regional]
total = sum(values)
print([r[0] for r in regional])
print(values)
print(total)
