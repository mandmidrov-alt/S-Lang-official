function double(x) -> Number:
    return x + x

function increment(value) -> Number:
    return add_one(value)

function add_one(x: Number) -> Number:
    return x + 1

let a = double(7)
let b = increment(10)

show a
show b
