record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

function promote(person: Person) -> Person:
    return Person(person.name, person.age + 10, person.active)

let people = [Person("Ada", 36, true), Person("Lin", 27, true), Person("Bob", 15, false)]
active = people where row.active == true
ordered = active sort by row.age asc
changed = ordered map upgrade(row)
changed_again = changed map promote(row)
total = changed_again sum row.age
show total
