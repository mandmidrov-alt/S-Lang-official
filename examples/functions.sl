function score_ratio(score: Number, age: Number) -> Number:
    return score / age

data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

selected = students where score_ratio(score, age) > 4
selected sort by score_ratio(score, age) desc
show selected
