record Person:
    name: Text
    age: Number

function is_adult(person: Person) -> Boolean:
    return person.age >= 18

let ada = Person("Ada", 36)
let bob = Person("Bob", 15)
let people = [ada, bob]

adults = people where age >= 18
names = adults map name

show names
show is_adult(ada)
show keys(ada)
show get(ada, "age")
