data people:
    a age 20
    b age 30
    c age 40
let older = false
result = people |> if older then where age >= 40 else where age >= 30
show result
