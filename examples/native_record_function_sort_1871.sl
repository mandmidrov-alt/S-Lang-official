record Person:
    name: Text
    age: Number
    active: Boolean

function upgrade(person: Person) -> Person:
    return Person(person.name, person.age + 1, person.active)

let people = [Person("Ada", 36, true), Person("Bob", 15, false), Person("Lin", 27, true)]
active = people where row.active == true
changed = active map upgrade(row)
ordered = changed sort by row.age asc
ages = ordered map row.age
show ages
