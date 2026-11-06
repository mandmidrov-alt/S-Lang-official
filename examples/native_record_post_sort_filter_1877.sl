record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 27, true), Person("Bob", 15, false), Person("Max", 34, true)]
changed = people map upgrade(row)
ordered = changed sort by row.age asc
selected = ordered where row.age >= 28
changed_again = selected map upgrade(row)
total = changed_again sum row.age
show total
