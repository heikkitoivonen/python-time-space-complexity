# codeop Module Complexity

The `codeop` module is the compile step of an interactive interpreter: it decides whether a piece
of source is a complete statement, an incomplete one that needs another line, or a syntax error,
and it can remember `__future__` statements from one input to the next. Every call compiles the
source it is given from scratch.

`n` is the length of the source passed to one call. The compiler's own work - parsing, building
the syntax tree and the code object - is O(n), and so is everything here that compiles.

## Complexity Reference

### compile_command

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codeop.compile_command(source, filename="<input>", symbol="single")` | O(n) | O(n) | A code object for complete input, `None` for incomplete input, `SyntaxError` for invalid input; remembers nothing between calls |

### Compile

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codeop.Compile()` | O(1) | O(1) | |
| Calling a `Compile` instance: `compiler(source, filename, symbol)` | O(n) | O(n) | Takes the source, filename and mode arguments of the built-in `compile()`; `__future__` statements it has compiled stay in force for later calls |

### CommandCompiler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codeop.CommandCompiler()` | O(1) | O(1) | |
| Calling a `CommandCompiler` instance: `compiler(source, filename="<input>", symbol="single")` | O(n) | O(n) | Answers as `compile_command()` does, and remembers `__future__` statements like `Compile` |

## Checking Whether Input Is Complete

An interactive loop compiles everything typed so far each time a line arrives, so each line costs
O(n) in the statement entered so far, not just in the new line.

```python
import codeop

code = codeop.compile_command('print("hello")')   # O(n)
assert code is not None

assert codeop.compile_command("if True:") is None  # O(n): needs another line

try:
    codeop.compile_command("if True")          # O(n)
except SyntaxError:
    pass
else:
    raise AssertionError("an invalid statement should raise SyntaxError")
```

## Remembering `__future__` Statements

`compile_command()` starts afresh on every call. A `CommandCompiler` - or a `Compile`, for the
source, filename and mode arguments of `compile()` - keeps the compiler flags that a `__future__` statement turned on and
applies them to every later input, which is what an interpreter session needs.

```python
import __future__
import codeop

flag = __future__.annotations.compiler_flag

session = codeop.CommandCompiler()
session("from __future__ import annotations")   # O(n)
assert session("x = 1").co_flags & flag          # still in force

assert not codeop.compile_command("x = 1").co_flags & flag  # forgotten

compiler = codeop.Compile()
compiler("from __future__ import annotations", "<input>", "exec")  # O(n)
assert compiler("x = 1", "<input>", "exec").co_flags & flag
```

## Related Modules

- **[code](code.md)** - `InteractiveConsole`, the read-eval loop built on `CommandCompiler`
- **[ast](ast.md)** - parse without compiling
- **[compile()](../builtins/compile.md)** - the built-in these functions wrap
