# Practical generic-record workflow with nested collection inference.
record Box<T>:
    value: T

function first_value(box: Box<List<Number>>):
    return first(box.value)

let numbers = Box([10, 20, 30])
let answer = first_value(numbers)
show answer
