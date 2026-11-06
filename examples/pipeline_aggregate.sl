data people:
    Clara age 34 score 96
    Denis age 41 score 88
    Elena age 23 score 91
    Gina age 37 score 94

total = people |> where age >= 30 |> sum score
show total
