# Practical data pipeline: filter, transform, aggregate and rank.
data orders:
    Anna age 28 score 81
    Boris age 17 score 64
    Clara age 34 score 96
    Denis age 41 score 88
    Elena age 23 score 91
    Farid age 16 score 70
    Gina age 37 score 94
    Hugo age 29 score 86

adults = orders where age >= 18
qualified = adults where score >= 85
points = qualified map score * 2
total = qualified sum score
average = qualified average score
qualified sort by score desc
show qualified
show points
show total
show average
