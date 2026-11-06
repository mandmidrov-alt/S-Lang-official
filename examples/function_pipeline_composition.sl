function double(x: Number) -> Number:
    return x * 2

function increment(x: Number) -> Number:
    return x + 1

let values = [1, 2, 3]

result = values |> map compose(double, increment)
show result
