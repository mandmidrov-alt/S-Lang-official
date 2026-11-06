# S-Lang 1.12.76: index values by a computed key.
# Duplicate keys are rejected instead of silently overwriting data.

people = [
  {"id": 101, "name": "Ada"},
  {"id": 102, "name": "Linus"},
  {"id": 103, "name": "Grace"}
]

people_by_id = index_by_values(people, value -> value.id)
