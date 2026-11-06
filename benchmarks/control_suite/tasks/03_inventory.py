items=[("bolts",2.5,100),("plates",12,20),("motors",80,4),("cables",5,50)]
values=[p*q for _,p,q in items]
print(values); print(sum(values)); print(min(values)); print(max(values))
