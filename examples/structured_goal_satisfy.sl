module structured_goal_satisfy

entity Point:
    x: Number
    y: Number

let upper = 10

sequence path from Point(0, 0) for up to 8 steps toward Point(10, 10) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 2)
    satisfy (candidate.x <= upper and candidate.y <= upper) and not (candidate.x == value.x and candidate.y == value.y)

show path
