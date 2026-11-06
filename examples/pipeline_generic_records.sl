record Box<T>:
    value: T

let boxes = [Box(1), Box(3), Box(2), Box(5)]
result = boxes |> where value >= 2 |> sort by value desc |> map value |> reduce 0 with acc + item
show result
