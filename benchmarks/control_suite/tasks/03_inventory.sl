data inventory:
    bolts price 2.5 quantity 100
    plates price 12 quantity 20
    motors price 80 quantity 4
    cables price 5 quantity 50

values = inventory map price * quantity
total = values reduce 0 with acc + item
minimum = values min item
maximum = values max item
show values
show total
show minimum
show maximum
