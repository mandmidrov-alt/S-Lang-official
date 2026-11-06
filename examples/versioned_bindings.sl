data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95

selected = people where age >= 18
selected sort by score desc
selected = selected map score
total = selected sum item
show total
