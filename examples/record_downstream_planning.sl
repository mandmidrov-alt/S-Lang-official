record Person:
    name: Text
    age: Number
    active: Boolean

record Summary:
    label: Text
    value: Number
    ok: Boolean

let people = [Person("Ada", 20, true), Person("Bob", 30, false)]
summaries = people map Summary(row.name, row.age + 1, row.active)
finals = summaries map Summary(row.label, row.value * 2, row.ok)
ordered = finals sort by row.value desc
show ordered
