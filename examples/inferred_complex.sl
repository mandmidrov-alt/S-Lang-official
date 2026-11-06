function first_number(values: List<Number>) -> Number:
    return first(values)

function unwrap(values) -> Number:
    return first_number(values)

let result = unwrap([10, 20, 30])
show result
