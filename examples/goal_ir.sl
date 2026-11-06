data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 25 score 72

best = choose candidate from people where age >= 18 maximizing score

graph roads:
    A -> B cost 2
    B -> D cost 2
    A -> C cost 1
    C -> D cost 5

route = find path from A to D in roads minimizing cost

solution = satisfy:
    x in 1..10
    y in 1..10
    x + y == 12
    x < y

show best, route, solution
