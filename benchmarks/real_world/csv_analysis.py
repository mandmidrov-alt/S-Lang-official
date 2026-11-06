import csv
with open("benchmarks/real_world/data/people.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
adults = [r for r in rows if int(r["age"]) >= 18]
engineers = [r for r in adults if r["role"] == "engineer"]
scores = [int(r["score"]) for r in engineers]
print(sum(scores))
print(len(engineers))
