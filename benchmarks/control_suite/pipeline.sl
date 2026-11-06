data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 16 score 72
    Eve age 25 score 90
let total = students |> where age >= 18 |> sort by score desc |> map score * 2 |> sum
show total
