module core
export add, triple

function add(left: Number, right: Number) -> Number:
    return left + right

function triple(value: Number) -> Number:
    return value * 3

function private_helper(value: Number) -> Number:
    return value * 100
