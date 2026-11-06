record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15), Person("Lin", 29)]
adults = people where age >= 18
names = adults map name
repacked = adults map Person(item.name, item.age)
summary = repacked reduce Person("none", 0) with Person(acc.name, acc.age + item.age)

let groups = [[Person("Ada", 36)], [Person("Bob", 15), Person("Lin", 29)]]
flat_groups = groups map item

show names
show repacked
show summary
show flat_groups
