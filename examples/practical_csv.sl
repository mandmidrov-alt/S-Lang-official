# Practical external-data workflow: CSV -> typed numeric pipeline.
let rows = read_csv("people.csv")
adults = rows where to_number(item.age) >= 30
ages = adults map to_number(item.age)
total = ages reduce 0 with acc + item
show total
show csv_headers(rows)
