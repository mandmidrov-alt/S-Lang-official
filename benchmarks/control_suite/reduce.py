from functools import reduce
numbers=[1,2,3,4,5]
print(reduce(lambda acc,value: acc*value,numbers,1))
