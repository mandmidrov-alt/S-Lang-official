data values:
    a value 4
    b value 5
    c value 6
let enabled = true
result = values |> if enabled then map value * 10 else map value * 2
show result
