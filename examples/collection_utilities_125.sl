# Compact collection utilities.
let values = [3, 1, 3, 2, 1, 4, 2, 5]
let unique = distinct(values)
let head = take(unique, 3)
let tail = skip(unique, 2)
show unique
show head
show tail
