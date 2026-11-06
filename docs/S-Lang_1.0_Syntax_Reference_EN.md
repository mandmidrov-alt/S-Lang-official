# S-Lang 1.0 — Normative Syntax Reference

**Release line:** 1.0  
**Source of truth:** the parser and semantic validator in this source archive, together with the conformance tests.  
**User manual:** `docs/latex/S-Lang_1.0_User_Manual_EN.tex`.

## Core rules

- Source files use the `.sl` extension.
- Names are case-sensitive.
- `#` begins a comment outside a quoted string and continues to the end of the physical line.
- Blocks use a colon followed by an indented body.
- Use `let name = expression` for ordinary bindings.
- Use `state name = expression` for mutable state and `set name = expression` to update it.
- Declare functions with `function`.
- A pipeline (`|>`) must remain on one physical line.
- Do not assume that syntax from Python, JavaScript, Rust, or SQL is valid in S-Lang.

## Values and expressions

```slang
let whole = 12
let decimal = 2.5
let enabled = true
let title = "S-Lang"
let values = [1, 2, 3]
let person = {name: "Ada", age: 36}
let result = if enabled then person.age + whole else whole
show result
```

Supported expression operators include exponentiation `^`, unary `+` and `-`, `not`, `*`, `/`, `%`, `+`, `-`, comparisons `==`, `!=`, `<`, `<=`, `>`, `>=`, and logical `and` / `or`. Conditional expressions use `if condition then value_a else value_b`.

List indexing (`values[0]`) and lambda expressions (`x -> x * 2`) are not part of the S-Lang 1.0 grammar.

## Bindings and conditions

```slang
state counter = 0
set counter = counter + 1

let score = 82
let grade = if score >= 75 then "pass" else "review"

if score >= 90:
    show "excellent"
else:
    show grade
```

## Functions, records, entities, and properties

```slang
function square(value: Number) -> Number:
    return value * value

function identity<T>(value: T) -> T:
    return value

record Person:
    name: Text
    age: Number

entity Circle:
    radius: m

property Circle.diameter -> m:
    return self.radius * 2

let person = Person("Ada", 36)
let circle = Circle(4 m)
show square(person.age), circle.diameter
```

## Collections

```slang
let numbers = [1, 2, 3, 4, 5]
let selected = numbers where item >= 3
let doubled = selected map item * 2
let ordered = doubled sort by item desc
let total = ordered sum item
let count = ordered count
let reduced = ordered reduce 0 with acc + item
```

Collection operations include `where`, `map`, `sort by`, `sum`, `count`, `max`, `min`, `average` / `avg`, `any`, `all`, and `reduce`.

In `reduce`, `acc` is the accumulator and `item` / `row` refer to the current element. Use `item` for scalar elements. For record elements, use `row.field` or `item.field`. A bare field name (such as `value`) resolves to a field on the current record in collection context; it is not an alias for a scalar list element.

## Pipelines

```slang
let numbers = [1, 2, 3, 4, 5]
let explicit = numbers |> where item >= 3 |> map item * 2 |> sort by item desc |> sum
let compact = numbers |> where >= 3 |> map * 2 |> sum
let records = [{score: 10}, {score: 20}]
let high = records |> where .score >= 15 |> sort by .score desc
```

Inside a pipeline, `item` and `row` refer to the current element. A leading comparison or arithmetic operator is shorthand for an operation on the current element (`where >= 3`, `map * 2`). A leading `.field` is shorthand for the current record's field. Pipeline stages must not be split across physical lines.

## Modules

```slang
module geometry
import "geometry.sl" as geo
import std.math
import "geometry.sl" {Circle, circumference}
export Circle, circumference
export {Circle} from "geometry.sl"
```

Standard module names are registered in `slang/stdlib/modules.py`. Public standard-library functions are catalogued in `slang/stdlib/catalog.py` and implemented in `slang/stdlib/registry.py`.

## Domain constructs

The language includes statement-level constructs for `data`, `sequence`, `graph`, `physics`, `body`, `simulate`, `choose`, `satisfy`, `find path`, and `circle`. These constructs have domain-specific syntax and constraints; they are not general-purpose expression forms. See the LaTeX user manual and the conformance tests for examples.

## Standard-library modules

The public module registry contains 13 modules:

- `std.aggregate`
- `std.analytics`
- `std.collections`
- `std.csv`
- `std.data`
- `std.datetime`
- `std.files`
- `std.json`
- `std.math`
- `std.path`
- `std.process`
- `std.relational`
- `std.text`

The complete function-name catalog is included in the LaTeX manual and generated from `slang/stdlib/catalog.py`.

## Validation

```text
slang version
slang check program.sl
slang run program.sl
slang run --native-jit program.sl
```

On Windows, use `slang1.0.exe` in place of `slang` unless the installation provides a command alias.

A successful `slang check` confirms syntax and semantic validity. It does not guarantee that every backend supports every construct. Check backend capabilities separately.

## Unsupported forms

The S-Lang 1.0 grammar does not include:

- `for` and `while` statement loops;
- lambda expressions such as `x -> x * 2`;
- list indexing such as `values[0]`;
- multi-line pipelines;
- `fn` as an alternative to `function`;
- bare assignment as a universal variable declaration;
- top-level `return` outside a valid function body.

## Change control

The parser (`slang/core.py`) defines accepted syntax. Semantic and type validation are implemented in `slang/semantic.py`, `slang/types.py`, and `slang/ast.py`. Runtime tests define execution support. Editor grammars are tooling aids, not normative specifications.

A syntax change must update the parser, semantic rules where applicable, positive and negative conformance tests, editor integrations, user documentation, and changelog together.
