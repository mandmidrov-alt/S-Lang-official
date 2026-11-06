# Goal-oriented graph example: the program states the path objective, not the search algorithm.
graph roads:
    A -> B cost 2
    B -> D cost 2
    A -> C cost 1
    C -> D cost 5
    D <-> E cost 1

route = find path from A to D in roads minimizing cost
show route
