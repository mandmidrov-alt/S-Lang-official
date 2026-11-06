data orders:
    Anna age 28 score 81
    Boris age 17 score 64
    Clara age 34 score 96
    Denis age 41 score 88
    Elena age 23 score 91

result = orders |> where age >= 18 |> where score >= 85 |> map score * 2 |> sum item
show result
