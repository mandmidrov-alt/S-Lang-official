students=[("Alice",22,91),("Bob",17,88),("Carol",31,95),("Dave",16,72),("Eve",25,90),("Frank",20,84)]
eligible=sorted([s for s in students if s[1]>=18], key=lambda s:s[2], reverse=True)
scores=[s[2] for s in eligible]
best=max(scores); average=sum(scores)/len(scores)
print([s[0] for s in eligible]); print(scores); print(best); print(average)
