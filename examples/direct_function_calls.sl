function double(x: Number) -> Number:
    return x * 2

function apply_twice(f, x: Number) -> Number:
    return f(f(x))

let transform = double
result = transform(5)
show result

result2 = apply_twice(transform, 3)
show result2
