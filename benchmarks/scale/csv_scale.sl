let rows = read_csv("people_50000.csv")
adults = rows where to_number(item.age) >= 18
engineers = adults where item.role == "engineer"
scores = engineers map to_number(item.score)
total = scores reduce 0 with acc + item
show total
