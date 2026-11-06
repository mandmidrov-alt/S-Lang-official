data people:
    Alice age 22 score 91
    Bob age 17 score 88
    Carol age 31 score 95
    Dave age 25 score 72
    Eve age 40 score 99

adults = people where age >= 18
elite = adults where score >= 90 and not (age < 30)
show elite
