function adjusted(x: Number) -> Number:
    let doubled = x * 2
    return doubled + 3

let value = adjusted(5)

data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

adults = people where age >= 18
best = choose candidate from adults maximizing score
scores = adults map score
total = scores sum item
