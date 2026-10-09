# eval() Function Complexity

The `eval()` function evaluates one Python expression and returns its value. Given a string, it
compiles the string first, on every call: nothing is cached. Given a code object from
[compile()](compile.md), it skips compilation and only runs the code.

`n` is the length of the source: characters in a `str`, bytes in a `bytes`. `v` is the local
variables in the function that calls `eval()`. The expression's own cost - the calls it makes, the
objects it builds - belongs to the expression and is added to every bound below.

## Complexity Reference

### eval()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `eval(source)` with a `str` or `bytes` source | O(n) + the expression's cost | O(n) + the expression's cost | Compiles on every call; leading spaces and tabs are skipped |
| `eval(code)` with a code object | The expression's cost | The expression's cost | No compilation. Code compiled in `'exec'` mode runs and returns `None`; code with free variables raises `TypeError` |
| `eval(source, globals)` | O(1) more | O(1) more | `globals` must be a `dict`; `__builtins__` is added to it if missing, and `locals` defaults to it |
| `eval(source, globals, locals)` | O(1) more | O(1) more | `locals` may be any mapping |
| `eval(source)` or `eval(code)` inside a function, without `globals` | O(v²) more on 3.13+, O(v) more on 3.11 and 3.12 | O(v) more | Copies the function's local variables into a dict on every call; passing `globals` skips the copy |
| Invalid source | O(n) | O(n) | Raises `SyntaxError`, for a statement or an empty string too; an undefined name raises `NameError` only when evaluated |

## Compile Once, Evaluate Many Times

`eval()` given a string compiles it every time. Compiling it once and passing the code object
leaves only the evaluation. An audit hook shows each compilation as it happens.

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

## Namespaces

Without arguments, `eval()` uses the caller's globals and locals. `globals` must be a real `dict`;
if it has no `__builtins__` key, `eval()` adds one, so builtins stay reachable. `locals` may be any
mapping, and defaults to `globals` when only `globals` is given.

```python
import collections

namespace = {"x": 10, "y": 20}
assert eval("x + y", namespace) == 30  # O(n)
assert "__builtins__" in namespace  # added on first use
assert eval("len('abc')", {}) == 3  # builtins are reachable from an empty dict

layers = collections.ChainMap({"a": 1}, {"b": 2})
assert eval("a + b", {}, layers) == 3  # locals may be any mapping

try:
    eval("a", layers)
except TypeError as error:
    assert "dict" in str(error)
else:
    raise AssertionError("a ChainMap was accepted as globals")
```

### Inside a Function

Called in a function with no namespaces, `eval()` first copies the function's local variables into
a dict, on every call. That is O(v) on 3.11 and 3.12 and O(v²) on 3.13+. Passing a dict as
`globals` skips the copy, which matters in a loop inside a function with many locals.

```python
def scaled(values, factor):
    results = []
    for value in values:
        results.append(eval("value * factor"))  # copies the locals, then O(n)
    return results

assert scaled([1, 2, 3], 10) == [10, 20, 30]

def scaled_with_namespace(values, factor):
    code = compile("value * factor", "<expr>", "eval")  # O(n), once
    namespace = {"factor": factor}
    results = []
    for value in values:
        namespace["value"] = value  # O(1)
        results.append(eval(code, namespace))  # no copy, no compilation
    return results

assert scaled_with_namespace([1, 2, 3], 10) == [10, 20, 30]
```

## Expressions Only

`eval()` takes one expression. A statement, or an empty string, is a `SyntaxError`; use
[exec()](exec.md) for statements. A code object compiled in `'exec'` mode is the exception: it
runs, and `eval()` returns `None`.

```python
try:
    eval("x = 5")
except SyntaxError:
    pass
else:
    raise AssertionError("eval() ran an assignment")

try:
    eval("")
except SyntaxError:
    pass
else:
    raise AssertionError("eval() accepted an empty string")

namespace = {}
assert eval(compile("x = 5", "<string>", "exec"), namespace) is None
assert namespace["x"] == 5

assert eval("  1 + 1") == 2  # leading spaces and tabs are skipped
```

## Safer Alternatives

`eval()` runs whatever the expression does, and an empty or restricted `__builtins__` does not
make it safe. For untrusted text that should hold a value, [`ast.literal_eval()`](../stdlib/ast.md)
parses it in O(n) and builds only literal values; an expression such as `__import__('os')`
raises `ValueError`.

```python
import ast

assert ast.literal_eval("[1, 2, 3]") == [1, 2, 3]  # O(n)
assert ast.literal_eval("{'a': 1, 'b': 2}") == {"a": 1, "b": 2}

try:
    ast.literal_eval("__import__('os')")
except ValueError as error:
    assert "malformed" in str(error)
else:
    raise AssertionError("literal_eval() made a call")
```

## Common Patterns

### Evaluating a Formula per Record

```python
formula = compile("price * quantity * (1 - discount)", "<formula>", "eval")  # O(n), once

orders = [
    {"price": 10.0, "quantity": 3, "discount": 0.0},
    {"price": 4.0, "quantity": 5, "discount": 0.5},
]
totals = [eval(formula, {"__builtins__": {}}, order) for order in orders]  # no compilation
assert totals == [30.0, 10.0]
```

## Performance Best Practices

✅ **Do**:

- Compile an expression once with `compile()` and pass the code object when it is evaluated
  repeatedly
- Pass a namespace dict when calling `eval()` in a loop inside a function, so the locals are not
  copied on every call
- Use `ast.literal_eval()` for text that should only hold a value

❌ **Avoid**:

- Calling `eval()` on a string inside a loop - it compiles the string every time
- Calling `eval()` on untrusted input, even with restricted `globals`
- Building code as strings for `eval()` where a function, a `lambda` or a dict lookup would do

## Version Notes

- **Python 3.13+**: `globals` and `locals` can be passed as keyword arguments
- **Python 3.13+**: Inside a function without namespaces, copying the locals costs O(v²) per call;
  it is O(v) on 3.11 and 3.12
- **All Python 3**: `eval()` runs arbitrary code; never pass it untrusted input

## Related Functions

- **[exec()](exec.md)** - Execute Python statements
- **[compile()](compile.md)** - Compile code objects
- **[ast.literal_eval()](https://docs.python.org/3/library/ast.html#ast.literal_eval)** - Safe literal evaluation
