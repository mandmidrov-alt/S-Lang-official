data people:
    Ada age 36 score 96
    Bob age 29 score 88
    Cara age 52 score 94
    Dan age 44 score 91

result = people |> where row.age >= 30 |> tee adults |> sort by row.score desc |> map row.score
older = adults |> where row.age >= 50 |> map row.score

show result, older
