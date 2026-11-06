values = [12,18,21,27,32,40]
total = sum(values)
average_value = total / len(values)
high = [x for x in values if x >= 25]
high_total = sum(high)
print(total); print(average_value); print(high_total); print(len(high))
