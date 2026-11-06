# S-Lang 1.12.77 — distinct_by_values

# Keep the first record for each computed category key.
records = [
    {"id": 1, "category": "a"},
    {"id": 2, "category": "b"},
    {"id": 3, "category": "a"},
]

unique_categories = distinct_by_values(records, item -> item.category)
