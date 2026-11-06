function identity<T>(value: T) -> T:
    return value

function first_value<T>(values: List<T>) -> T:
    return first(values)

function append_value<T>(values: List<T>, value: T) -> List<T>:
    return append(values, value)

let numbers = [1, 2, 3]
let texts = ["a", "b"]
let n = identity(42)
let first_number = first_value(numbers)
let more_numbers = append_value(numbers, 4)
let first_text = first_value(texts)

show n
show first_number
show more_numbers
show first_text
