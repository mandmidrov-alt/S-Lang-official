# S-Lang 1.1.3 — inferred function return types

function double(x: Number):
    return x + x

function identity(value: T):
    return value

function first_value(values: List<T>):
    return first(values)

let a = double(7)
let b = identity("hello")
let c = first_value([10, 20, 30])

show a
show b
show c
