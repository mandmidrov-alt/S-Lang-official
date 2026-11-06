let rows = read_csv("data/people.csv")
let total = rows |> where to_number(item.age) >= 18 and item.role == "engineer" |> map to_number(item.score) |> sum
let count = rows |> where to_number(item.age) >= 18 and item.role == "engineer" |> count
show total, count
