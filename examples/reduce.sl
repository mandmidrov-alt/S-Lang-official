# Record collection reduction: bare `value` is shorthand for the current
# record field. For scalar lists, use `item` (see reduce_numeric.sl).
data numbers:
    a value 1
    b value 2
    c value 3
    d value 4

product = numbers reduce 1 with acc * value
total = numbers reduce 0 with acc + value
show product, total
