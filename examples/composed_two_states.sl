entity Pair:
    a: Number
    b: Number

function next_pair(value: Pair) -> Pair:
    return Pair(value.b, value.a + value.b)

sequence left from Pair(1, 1) for 6 steps using next_pair(value)
sequence right from Pair(3, 3) for 6 steps using next_pair(value)
left_values = left map item.a
right_values = right map item.a
merged = left_values map item * 4
sum_right = right_values reduce 0 with acc + item
show left_values, right_values, merged, sum_right
