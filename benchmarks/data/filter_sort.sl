data people:
    Alice age 22
    Bob age 17
    Carol age 31
    Dave age 16
    Eve age 25
let adults = people |> where age >= 18 |> sort by age
show adults
