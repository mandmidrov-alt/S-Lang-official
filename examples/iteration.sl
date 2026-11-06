data students:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 16 score 72
    Eve age 25 score 90

adults = students where age >= 18
values = adults map score * 2
total = students sum score
average = students average score
count = students count
adults sort by score desc
show adults
show values
show total
show average
show count
