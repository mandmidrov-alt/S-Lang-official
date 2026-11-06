function make_multiplier(factor: Number) -> Function<Number, Number>:
    function multiply(x: Number) -> Number:
        return x * factor
    return multiply

let double = make_multiplier(2)
let triple = make_multiplier(3)

result = double(5)
show result
