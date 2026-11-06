function identity(value: T):
    return value

function unwrap(values) -> Number:
    let nested = identity(values)
    let inner = first(nested)
    return first(inner)

let value = unwrap([[7, 8]])
show value
