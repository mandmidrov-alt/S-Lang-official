# Structured state is carried through the sequence as one semantic value.
entity Pair:
    a: Number
    b: Number

function next_pair(value: Pair) -> Pair:
    return Pair(value.b, value.a + value.b)

sequence states from Pair(0, 1) for 10 steps using next_pair(value)
values = states map item.a
show values
