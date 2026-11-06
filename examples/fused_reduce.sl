data numbers:
    a value 1
    b value 2
    c value 3
    d value 4

filtered = numbers where value >= 2
scaled = filtered map value * 2
total = scaled reduce 0 with acc + item
show total
