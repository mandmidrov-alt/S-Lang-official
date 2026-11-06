data values:
    a value 1
    b value 2
    c value 3
    d value 4

result = values |> where value >= 2 |> map value * 10
show result
