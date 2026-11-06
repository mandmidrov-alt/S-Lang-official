# S-Lang Design Principles: Readability First

**Status:** project-level design constraint. New language features and refactors should be reviewed against this document.

## Purpose

S-Lang is a high-level general-purpose programming language intended to make ordinary programs understandable to people who are not professional programmers. Readability is a core product requirement, not a cosmetic preference.

## Non-negotiable principles

1. **Readable by default.** Common code should be understandable from its structure and names without requiring knowledge of compiler internals or low-level computer architecture.
2. **High-level by default.** Memory management, JIT compilation, native code generation, and backend details remain implementation concerns for ordinary users.
3. **Few, consistent rules.** Similar constructs should behave similarly. Avoid special cases, hidden evaluation-order surprises, and multiple ways to express the same simple operation unless they provide a clear benefit.
4. **Errors explain how to recover.** Diagnostics should identify the relevant source location, explain the problem in plain language, and offer a correction when practical.
5. **Advanced features stay optional.** Low-level or expert-only capabilities must not be prerequisites for everyday programs. If introduced, keep them in a clearly separated advanced layer.
6. **Expressiveness without syntax bloat.** Prefer a small number of composable constructs over a growing collection of keywords and exceptions.
7. **Documentation matches reality.** Every documented example should be checked against executable behavior where practical. Unsupported syntax and backend limitations must be stated explicitly.
8. **Compatibility is deliberate.** Changes to syntax, typing, evaluation, or standard-library behavior require regression tests and a clear compatibility note.
9. **Measure human usability.** For representative examples, test whether readers can explain what the program does and safely make a small change without needing to understand the implementation.
10. **Correctness before cleverness.** Do not trade predictable behavior for a shorter implementation, an impressive benchmark, or a feature-count target.

## Feature acceptance checklist

Before accepting a language feature or major refactor, ask:

- Does it make a common task easier without making ordinary code harder to read?
- Can a beginner infer its meaning from the syntax and nearby names?
- Does it reuse existing rules rather than introduce an isolated exception?
- Are failure cases diagnosed clearly?
- Are examples, Russian and English documentation, and regression tests updated together?
- Does it preserve the high-level default and keep advanced complexity optional?
- If readability worsens materially, can the feature be simplified, made opt-in, or excluded from the core language?

A feature that fails the readability test should not be added to the core syntax until its design is revised.

## Illustrative style

Prefer clear, composable steps such as:

```slang
let adults = people
    .where(person => person.age >= 18)
    .sort_by(person => person.name)

for person in adults {
    print(person.name)
}
```

This example is illustrative; actual syntax support must be verified against the current syntax reference and executable tests before it is advertised as supported.

## Release review

Every release audit should state whether changes preserve these principles. A passing test suite alone does not prove usability; a readable example alone does not prove correctness. Both matter.
## Standard library and catalog

Every public standard-library function must have a human-readable catalog description. The description should explain the function purpose rather than merely repeat its identifier. The catalog should consistently expose module, effect, and required capability; metadata completeness is enforced by a regression test.

## Consistent standard-library validation

Functions that accept counts, indexes, strides, or window sizes should apply the same validation rules: reject booleans, fractional values, and non-finite floats; accept integer-valued floats where documented; and return clear type/value errors rather than silently truncating values or leaking incidental conversion exceptions.

### Unknown-function diagnostics

For a misspelled function name, the compiler may suggest a close name from the standard library or declared functions. If the match is ambiguous, it lists alternatives; if similarity is weak, it keeps the generic message. The diagnostic code and structured payload remain stable for tool compatibility.
