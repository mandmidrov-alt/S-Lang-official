let people = read_csv("people_pipeline.csv")
result = people |> where to_number(row.age) >= 18 |> sort by to_number(row.score) desc |> map to_number(row.score) |> average item
show result
