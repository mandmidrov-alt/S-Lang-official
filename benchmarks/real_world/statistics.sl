let values = [12, 18, 21, 27, 32, 40]
let total = values sum
let average_value = values average
let high_total = values |> where >= 25 |> sum
let count = values |> where >= 25 |> count
show total, average_value, high_total, count
