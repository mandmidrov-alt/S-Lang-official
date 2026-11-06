# Practical bounded allocation: satisfy the declared constraints.
solution = satisfy:
    workers in 1..12
    machines in 1..8
    workers + machines == 14
    workers > machines
    workers < 10

show solution
