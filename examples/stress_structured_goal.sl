module stress_structured_goal

entity Point:
    x: Number
    y: Number

let lower = 0
let upper = 10

sequence path from Point(0, 0) for up to 6 steps toward Point(8, 8) choosing:
    Point(value.x + 1, value.y)
    Point(value.x, value.y + 2)
    Point(value.x + 2, value.y + 2)
    satisfy candidate.x >= lower
    satisfy candidate.y >= lower
    satisfy candidate.x <= upper and candidate.y <= upper
    satisfy not (candidate.x == value.x and candidate.y == value.y)

show path
