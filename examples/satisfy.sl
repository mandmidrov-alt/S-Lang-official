# Finite constraint solving as a semantic goal.
solution = satisfy:
    x in 1..10
    y in 1..10
    x + y == 12
    x < y

show solution
