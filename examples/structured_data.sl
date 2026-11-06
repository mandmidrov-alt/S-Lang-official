# S-Lang 1.0.5 structured data example
let person = {name: "Ada", role: "researcher", age: 36}
let summary = {name: person.name, adult: person.age >= 18}
show person.name
show get(person, "role")
show has(person, "age")
show keys(summary)
