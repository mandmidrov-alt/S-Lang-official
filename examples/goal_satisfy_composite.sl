module goal_satisfy_composite

let lower_limit = 2
let upper_limit = 20

sequence path from 1 for up to 8 steps toward 18 choosing:
    value + 1
    value + 3
    value * 2
    satisfy (candidate >= lower_limit and candidate <= upper_limit) and not (candidate == value)

show path
