function double(x: Number) -> Number:
    return x * 2

function positive(x: Number) -> Boolean:
    return x > 0

let transform = double
let values = [0, 1, 2, 3]

let applied = apply(transform, 5)
result = values |> where positive |> map transform

show applied
show result
