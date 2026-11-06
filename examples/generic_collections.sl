record Person:
    name: Text
    age: Number

function adults(people: List<Person>) -> List<Person>:
    return people

function identity_matrix(values: List<List<Number>>) -> List<List<Number>>:
    return values

let people = [Person("Ada", 36), Person("Bob", 15)]
let checked = adults(people)
let matrix = identity_matrix([[1, 2], [3, 4]])

show checked
show matrix
