# S-Lang 1.0.4 CSV analysis example
let rows = read_csv("people.csv")
adults = rows where item.age >= "30"
ages = adults map to_number(item.age)
total = ages reduce 0 with acc + item
show total
show csv_headers(rows)
