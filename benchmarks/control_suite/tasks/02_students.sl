data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 16 score 72
    Eve age 25 score 90
    Frank age 20 score 84

eligible = students where age >= 18
eligible sort by score desc
scores = eligible map score
best = eligible max score
average = eligible average score
show eligible
show scores
show best
show average
