data values:
    a value 1
    b value 2
    c value 3
    d value 4
let enabled = true
result = values |> if enabled then where value >= 2 |> map value * 10 |> sum item else where value >= 3 |> reduce 0 with acc + value
show result
