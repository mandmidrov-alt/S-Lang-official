record Box<T>:
    value: T

function first_number(box: Box<List<Number>>) -> Number:
    return first(box.value)

let numbers = Box([10, 20, 30])
let answer = first_number(numbers)

show answer
