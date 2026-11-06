# Numeric collection reduction: item is the current scalar element.
let numbers = [1, 2, 3, 4]
product = numbers reduce 1 with acc * item
total = numbers reduce 0 with acc + item
show product, total
