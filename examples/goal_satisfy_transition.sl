module goal_satisfy_transition

sequence path from 1 for up to 8 steps toward 20 choosing:
    value + 1
    value + 3
    value * 2
    satisfy candidate <= 20

show path
