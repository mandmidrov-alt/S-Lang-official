function adjusted_score(score: Number, bonus: Number) -> Number:
    let boosted = score + bonus
    let normalized = boosted / 2
    return normalized

data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

selected = students where adjusted_score(score, 9) > 48
selected sort by adjusted_score(score, 9) desc
show selected
