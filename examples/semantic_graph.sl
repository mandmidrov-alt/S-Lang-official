data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

adults = people where age >= 18
ranked = adults sort by score desc
best = choose candidate from ranked maximizing score
scores = ranked map score
total = scores sum item
show best, total
