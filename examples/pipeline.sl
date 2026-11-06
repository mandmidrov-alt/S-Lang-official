data people:
    Clara age 34 score 96
    Denis age 41 score 88
    Elena age 23 score 91
    Gina age 37 score 94

result = people |> where row.age >= 30 |> sort by row.score desc |> map row.score
show result
