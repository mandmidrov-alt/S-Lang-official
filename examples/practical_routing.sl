# Practical route planning: the program describes the route objective.
graph network:
    Home -> A cost 4
    Home -> B cost 2
    A -> C cost 3
    B -> C cost 1
    B -> D cost 7
    C -> D cost 2
    D -> Office cost 3
    C -> Office cost 8

route = find path from Home to Office in network minimizing cost
show route
