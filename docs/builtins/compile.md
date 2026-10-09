# compile() Function Complexity

The `compile()` function turns Python source, or an `ast` tree, into a code object that `eval()`
and `exec()` run. It tokenizes, parses, builds a symbol table and emits bytecode, and each stage
is linear in the source. Nothing is cached: compiling the same source twice compiles it twice,
and `eval()` or `exec()` given a string compiles it on every call.

`n` is the length of the source: characters in a `str`, bytes in a `bytes`. `t` is the nodes in
an `ast` tree, counting each item of a tuple or frozenset held by an `ast.Constant`. Running the code object is not part of `compile()`; its cost is whatever the
compiled code does.

## Complexity Reference

### compile()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compile(source, filename, mode)` with a `str` or `bytes` source | O(n) | O(n) | No cache: the same source compiled again costs O(n) again. Constant folding has size limits, so a short expression such as `'a' * 10**8` is left for run time rather than built while compiling |
| `mode='exec'`, `mode='eval'`, `mode='single'` | O(n) | O(n) | `'exec'` takes statements, `'eval'` one expression, `'single'` one interactive statement whose expression values are printed |
| `compile(source, filename, mode, flags=ast.PyCF_ONLY_AST)` | O(n) | O(n) | Stops after parsing and returns the `ast` tree, as `ast.parse()` does |
| `compile(tree, filename, mode)` with an `ast` tree | O(t) | O(t) | The tree is validated first; nodes built by hand need line numbers, which `ast.fix_missing_locations()` fills in |
| `optimize=-1`, `0`, `1`, `2` | O(n) | O(n) | `-1` follows the interpreter's `-O`; `1` removes `assert` statements and makes `__debug__` false; `2` also removes docstrings |
| `flags`, `dont_inherit` | O(n) | O(n) | Future features and `ast.PyCF_*` options. By default the caller's `from __future__` imports apply as well; `dont_inherit=True` uses `flags` alone |
| Invalid source | O(n) | O(n) | Raises `SyntaxError` with `filename` and the line, scoping errors such as a `nonlocal` with no binding included; an undefined name is not an error until the code runs |

### Running the result

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `eval(code)`, `exec(code)` | The code's own cost | The code's own cost | No compilation; see [eval()](eval.md) and [exec()](exec.md) |
| `eval(string)`, `exec(string)` | O(n) + the code's cost | O(n) + the code's cost | Compiles the string on every call |

## Compile Once, Run Many Times

`eval()` and `exec()` given a string compile it every time. Compiling it once and passing the
code object leaves only the run. An audit hook shows each compilation as it happens.

```python
import sys

compiled = []
sys.addaudithook(lambda event, args: compiled.append(args[1]) if event == "compile" else None)

x = 3
for _ in range(100):
    assert eval("x ** 2") == 9  # O(n) per call - compiles the string each time
assert compiled.count("<string>") == 100

code = compile("x ** 2", "<expr>", "eval")  # O(n), once
for _ in range(100):
    assert eval(code) == 9  # no compilation, only the expression runs
assert compiled.count("<expr>") == 1
```

## Modes

The mode decides what the source may contain, not what compiling it costs. `'single'` is the
interactive prompt's mode: an expression statement prints its value unless it is `None`.

```python
import contextlib
import io

code = compile("2 + 3", "<string>", "eval")  # O(n) - one expression
assert eval(code) == 5

code = compile("x = 10\ny = 20\nz = x + y\n", "<string>", "exec")  # O(n) - statements
namespace = {}
exec(code, namespace)
assert namespace["z"] == 30

code = compile("1 + 1", "<string>", "single")  # O(n) - one interactive statement
output = io.StringIO()
with contextlib.redirect_stdout(output):
    exec(code)
assert output.getvalue() == "2\n"

try:
    compile("x = 1\ny = 2", "<string>", "single")
except SyntaxError as error:
    assert "multiple statements" in str(error)
else:
    raise AssertionError("'single' accepted two statements")
```

## Sources and Trees

A `bytes` source is decoded first, honouring a coding declaration, and costs O(n) in its bytes.
`ast.PyCF_ONLY_AST` stops after parsing and returns the tree; a tree passed back in is compiled
without parsing, so a program can parse once, transform the tree, and compile the result.

```python
import ast

code = compile(b"# -*- coding: latin-1 -*-\nname = '\xe9'\n", "<bytes>", "exec")  # O(n)
namespace = {}
exec(code, namespace)
assert namespace["name"] == "é"

tree = compile("total = price * count", "<string>", "exec", flags=ast.PyCF_ONLY_AST)  # O(n)
assert ast.dump(tree) == ast.dump(ast.parse("total = price * count"))

tree.body[0].value.op = ast.Add()  # turn the product into a sum
code = compile(tree, "<ast>", "exec")  # O(t)
namespace = {"price": 3, "count": 4}
exec(code, namespace)
assert namespace["total"] == 7
```

## Optimization Levels

`optimize` changes what is emitted, not the bound. Level 1 drops `assert` statements and compiles
`__debug__` as false; level 2 also drops docstrings.

```python
source = '''
def check(value):
    "Return value, which must be positive."
    assert value > 0
    return value
'''

namespace = {}
exec(compile(source, "<string>", "exec", optimize=0), namespace)  # O(n)
assert namespace["check"].__doc__ == "Return value, which must be positive."
try:
    namespace["check"](-1)
except AssertionError:
    pass
else:
    raise AssertionError("optimize=0 removed the assert")

exec(compile(source, "<string>", "exec", optimize=1), namespace)  # O(n)
assert namespace["check"](-1) == -1  # the assert is gone
assert namespace["check"].__doc__ is not None

exec(compile(source, "<string>", "exec", optimize=2), namespace)  # O(n)
assert namespace["check"].__doc__ is None  # and so is the docstring
```

## Future Features

`flags` takes a feature's `compiler_flag` from the `__future__` module. Without
`dont_inherit=True`, the features in force where `compile()` is called apply too.

```python
import __future__

source = "def area(width: float, height: float) -> float: return width * height"

code = compile(source, "<string>", "exec", flags=__future__.annotations.compiler_flag)
namespace = {}
exec(code, namespace)
assert namespace["area"].__annotations__ == {
    "width": "float", "height": "float", "return": "float"
}
```

## Limits on Nesting

Nesting depth has hard limits. More than 200 open brackets
raises `SyntaxError`, and a block indented 100 levels deep raises `IndentationError`. A chain the
grammar nests - `a + b + c + ...`, or an `if` with a long run of `elif` branches - deepens the tree
by one level per link, so a chain of 100,000 links raises `RecursionError` or `MemoryError` where
100,000 separate statements compile. Code that generates source should emit flat statements or a
lookup table rather than one long chain.

```python
try:
    compile("x = " + "(" * 201 + "1" + ")" * 201, "<string>", "exec")
except SyntaxError as error:
    assert "too many nested parentheses" in str(error)
else:
    raise AssertionError("201 nested brackets compiled")

# Flat: one statement per case
flat = "".join(f"if a == {i}: b = {i}\n" for i in range(10_000))
compile(flat, "<string>", "exec")  # O(n)
```

## Errors

`compile()` rejects invalid syntax, including scoping errors such as a `nonlocal` with no binding,
but not a name that does not exist: that only fails when the code runs. A `SyntaxError` names the
file and line it was given, which is why a meaningful `filename` helps.

```python
try:
    compile("total = ", "settings.py", "exec")
except SyntaxError as error:
    assert error.filename == "settings.py"
    assert error.lineno == 1
else:
    raise AssertionError("incomplete source compiled")

code = compile("undefined_function()", "<string>", "exec")  # compiles
try:
    exec(code, {})
except NameError as error:
    assert "undefined_function" in str(error)
else:
    raise AssertionError("an undefined name ran")
```

## Common Patterns

### Loading a Configuration Script

```python
config_script = """
DEBUG = True
DATABASE = "sqlite:///app.db"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
"""

code = compile(config_script, "config.py", "exec")  # O(n), once
config = {}
exec(code, config)
assert config["DEBUG"] is True
assert config["ALLOWED_HOSTS"] == ["localhost", "127.0.0.1"]
```

### Generating a Function

```python
func_source = """
def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
"""

namespace = {}
exec(compile(func_source, "<generated>", "exec"), namespace)  # O(n), once
fibonacci = namespace["fibonacci"]
assert [fibonacci(i) for i in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]
```

## Performance Best Practices

✅ **Do**:

- Compile source that runs repeatedly once, and pass the code object to `eval()` or `exec()`
- Keep the code object rather than the string; `compile()` caches nothing
- Pass a real `filename`, so a `SyntaxError` points at the right place
- Generate flat statements, not one long `elif` or `+` chain

❌ **Avoid**:

- Calling `compile()` before a single `eval()` or `exec()` - they compile a string anyway, at the
  same cost
- Treating `compile()` as validation of untrusted code: it rejects only invalid syntax, and running
  the result runs whatever the code does
- Relying on `assert` in code compiled with `optimize=1` or more, or under `python -O`

## Related Functions

- **[eval()](eval.md)** - Runs an expression, compiling a string on every call
- **[exec()](exec.md)** - Runs statements, compiling a string on every call
- **[ast](../stdlib/ast.md)** - Parse without compiling, and transform the tree before compiling it
- **[dis](../stdlib/dis.md)** - Disassemble the code object `compile()` returns
- **[`__future__`](../stdlib/__future__.md)** - The feature flags `compile()` accepts
- **[py_compile](../stdlib/py_compile.md)** - Compile a file to a `.pyc`
