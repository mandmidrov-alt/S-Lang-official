record Person:
    name: Text
    age: Number

let people = [Person("Ada", 36), Person("Bob", 15)]
ages = people map age
let all_ages = append([1, 2, 3], 42)
let first_age = first(all_ages)
let last_age = last(all_ages)
let groups = [[1, 2], [3, 4]]
let flat = flatten(groups)

show first_age
show last_age
show flat
