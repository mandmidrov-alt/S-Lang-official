students=[{"age":22,"score":91},{"age":17,"score":88},{"age":31,"score":95},{"age":16,"score":72},{"age":25,"score":90}]
adults=[x for x in students if x["age"]>=18]
ranked=sorted(adults,key=lambda x:x["score"],reverse=True)
values=[x["score"]*2 for x in ranked]
print(sum(values))
