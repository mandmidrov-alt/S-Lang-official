# Practical named-record workflow with inferred function types.
record Person:
    name: Text
    age: Number
    score: Number

let people = [Person("Anna", 28, 81), Person("Clara", 34, 96), Person("Denis", 41, 88)]
adults = people where age >= 30
scores = adults map score
scores sort by item desc
show adults
show scores
