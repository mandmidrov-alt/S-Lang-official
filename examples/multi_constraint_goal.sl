module multi_constraint_goal

entity Point:
    x: Number
    y: Number

let lower = 0
let upper = 10

sequence path from Point(0, 0) for up to 8 steps toward Point(6, 6) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 2)
    Point(value.x + 3, value.y + 3)
    satisfy candidate.x >= lower
    satisfy candidate.y >= lower
    satisfy candidate.x <= upper and candidate.y <= upper
    satisfy not (candidate.x == value.x and candidate.y == value.y)

show path
