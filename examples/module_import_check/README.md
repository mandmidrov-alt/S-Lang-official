# S-Lang 1.0 Module Import Regression Example

Run the following commands from this directory:

```powershell
slang1.0.exe check main.sl
slang1.0.exe run main.sl
```

On systems where the executable is available as `slang`, use that command name instead.

Expected program output:

```text
15
21
42
MODULE IMPORT CHECK PASS
```

This example verifies:

- importing a module file with an alias (`as api`);
- selectively importing a public function (`{ triple }`);
- importing the same module directly under a separate alias;
- re-exporting a function through two intermediate modules;
- calling imported functions from the final module.

The additional files `cycle_a.sl` and `cycle_b.sl` intentionally form a cycle. The check must report a `cyclic import` diagnostic rather than execute the program:

```powershell
slang1.0.exe check cycle_a.sl
```

The negative test is expected to return a non-zero exit code and report the cyclic import.

Private names must not be imported through a public module interface. A missing module file must produce an `import not found` diagnostic. These cases are also covered by automated regression tests.
