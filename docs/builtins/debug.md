# __debug__ Constant Complexity

The `__debug__` constant is the one builtin whose name never reaches a namespace: the compiler
substitutes its value into the code it is compiling. It is `True` unless the interpreter was
started with `-O` or `-OO`, and the choice is fixed when the code is compiled rather than when
it runs. Reading it therefore resolves nothing at run time - the value is already in the code
object - and the code it guards can cost nothing at all: an `assert`, and the body of an
`if __debug__:` block, are not emitted as bytecode once optimization is on.

It is a name, not a keyword. `True`, `False` and `None` are resolved by the lexer, so
`x.True` is not even syntax; `__debug__` is an ordinary identifier that the compiler refuses to
bind. That is why reading `x.__debug__` is legal while binding one is not.

`c` is what evaluating an assertion's condition costs, truth-testing it included, `m` what
building its message costs, and `b` what the block an `if __debug__:` guards costs. All three
are expressions the caller writes. Time below includes them. Space is what the statement holds
once the expression has been evaluated, rather than the workspace the expression needed to
produce it: an assertion holds nothing when it passes and its message when it fails, and a
guard holds whatever its block holds. Where a row says a statement is not compiled, no bytecode
is emitted for it: nothing inside it is evaluated, and nothing it would have allocated is
allocated.

## Complexity Reference

### The constant

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `__debug__` | O(1) | O(1) | Folded into the code object when it is compiled, so `co_names` stays empty and nothing is looked up at run time |
| `builtins.__debug__`, `getattr(builtins, "__debug__")` | O(1) | O(1) | A dict lookup, and a separate thing from the constant: the entry is set once at startup and read by nothing |
| `setattr(builtins, "__debug__", value)` | O(1) | O(1) | Accepted, and changes neither running code nor the next compilation |
| `x.__debug__` | O(1) | O(1) | An ordinary attribute load of a stored attribute, unaffected by the constant; `AttributeError` unless the object defines one, and a descriptor or `__getattribute__` of that name costs whatever it does |
| `__debug__ = v`, `del __debug__`, `x.__debug__ = v`, `f(__debug__=v)` | O(1) | O(1) | `SyntaxError` when the code is compiled, so it never runs. The name cannot be bound in any form: assignment, `del`, `def`, `class`, a parameter, a keyword argument, `import ... as`, `for`, `except ... as`, the walrus, or an attribute of another object |

### assert

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `assert cond` | O(c) | O(1) | The condition is evaluated every time the statement is reached |
| `assert cond, msg` | O(c), O(c + m) on failure | O(m) on failure | The message expression is built only when the condition is false |
| Either, under `-O` or `-OO` | O(1) | O(1) | Not compiled: no bytecode is emitted for the statement, so the condition is never evaluated. What the statement told the symbol table survives it |

### if __debug__ blocks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `if __debug__:` body | O(b) | O(b) | Whatever the block itself does |
| The same block under `-O` or `-OO` | O(1) | O(1) | The branch is dead at compile time and its bytecode is dropped, but the locals it bound keep their slots in `co_varnames`: unlike a dropped `assert`, the result is not the code object the source without the block would give |

### Choosing the level

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.flags.optimize` | O(1) | O(1) | 0, 1 or 2, fixed at startup by `-O` and `-OO` |
| `compile(source, filename, mode, optimize=level)` | O(n) | O(n) | n = source length. `-1` follows the interpreter's own flag, `0` keeps assertions, `1` drops them, `2` also drops docstrings |

## Nothing Is Looked Up

The name is replaced by its value at compile time, so the code object holds a constant and has
no name to resolve. That does not make the read free - the instruction still runs - it makes it
the same instruction a literal would compile to. Reaching the same value through the `builtins`
module is an ordinary lookup instead.

```python
import builtins

def reads_the_constant():
    return __debug__  # O(1) - a constant in the code object

assert reads_the_constant.__code__.co_names == ()  # nothing to look up
assert any(value is True for value in reads_the_constant.__code__.co_consts)
assert reads_the_constant() is True

assert getattr(builtins, "__debug__") is True  # O(1) - but a dict lookup
```

## Assertions Are Not Compiled Under -O

An assertion costs its condition on every run. Under `-O` the statement is gone from the
bytecode, so the condition is not evaluated at all - which is what makes an expensive
invariant check affordable, and what makes `assert` the wrong tool for validating input.

```python
calls = []

def condition():
    calls.append(1)
    return True

source = "assert condition(), 'never built'\n"

exec(compile(source, "<example>", "exec", optimize=0), {"condition": condition})
assert calls == [1]  # O(c) - the condition ran

exec(compile(source, "<example>", "exec", optimize=1), {"condition": condition})
assert calls == [1]  # not compiled, so it did not run again

# What is left is the code the source without the statement would give
with_assertion = "def f(x):\n    assert x > 0, 'bad'\n    return x\n"
without = "def f(x):\n    return x\n"
dropped: dict = {}
plain: dict = {}
exec(compile(with_assertion, "<example>", "exec", optimize=1), dropped)
exec(compile(without, "<example>", "exec"), plain)
assert dropped["f"].__code__.co_code == plain["f"].__code__.co_code
assert dropped["f"].__code__.co_varnames == plain["f"].__code__.co_varnames
```

The message is a second expression, and it is built only when the assertion fails.

```python
built = []

def message():
    built.append(1)
    return "failed"

exec(compile("assert True, message()", "<example>", "exec"), {"message": message})
assert built == []  # the assertion held, so nothing was built

try:
    exec(compile("assert False, message()", "<example>", "exec"), {"message": message})
except AssertionError as error:
    assert str(error) == "failed"
    assert built == [1]  # O(m), on failure only
else:
    raise AssertionError("a false assertion did not raise")
```

### What a Dropped Assertion Leaves Behind

The bytecode goes; what the statement told the symbol table does not. A name it binds, in the
condition or in the message, stays a local of the function unless a `global` or `nonlocal`
declaration puts it elsewhere - and only the binding goes, so a later read raises
`UnboundLocalError`, or quietly returns whatever another assignment left there. A name it reads
from an enclosing function stays a closure reference on both sides. A `yield` in it keeps the
function a generator, without the yield ever happening.

```python
import inspect

bound = "def f():\n    assert (saved := 1)\n    return saved\n"
shadowed = "def f():\n    saved = 2\n    assert (saved := 1)\n    return saved\n"
yielded = "def f():\n    assert (yield True)\n    return 1\n"
closing = "def f(value):\n    def inner():\n        assert value\n        return 1\n    return inner\n"


def build(source, level):
    namespace: dict = {}
    exec(compile(source, "<example>", "exec", optimize=level), namespace)
    return namespace["f"]


assert build(bound, 0)() == 1
assert build(bound, 1).__code__.co_varnames == ("saved",)  # still a local
try:
    build(bound, 1)()  # O(1) - and it never gets a value
except UnboundLocalError as error:
    assert "saved" in str(error)
else:
    raise AssertionError("the dropped binding still produced a value")

# With something else assigning it, the read succeeds and the answer changes
assert build(shadowed, 0)() == 1
assert build(shadowed, 1)() == 2

# A name read from an enclosing function stays a closure reference
assert build(closing, 1)(True).__code__.co_freevars == ("value",)

# And a yield survives as what it makes the function, without ever yielding
assert inspect.isgeneratorfunction(build(yielded, 0))
optimized = build(yielded, 1)
assert inspect.isgeneratorfunction(optimized)
try:
    next(optimized())  # O(1) - the yield is gone, so it finishes at once
except StopIteration as stop:
    assert stop.value == 1
else:
    raise AssertionError("the dropped yield still produced a value")
```

## Guarding Expensive Checks

`if __debug__:` is the same mechanism with a block instead of a condition. The branch is dead
at compile time, so its bytecode is dropped; what survives is the slots its locals took, which
is why this is not quite the same as never writing the block.

```python
source = (
    "def check(data):\n"
    "    if __debug__:\n"
    "        total = sum(data)\n"
    "        assert total >= 0\n"
    "    return len(data)\n"
)

compiled = {}
for level in (0, 1):
    namespace = {}
    exec(compile(source, "<example>", "exec", optimize=level), namespace)
    compiled[level] = namespace["check"].__code__

assert len(compiled[1].co_code) < len(compiled[0].co_code)  # the block is gone

# What the dropped block leaves behind
assert compiled[1].co_varnames == compiled[0].co_varnames
assert "total" in compiled[1].co_varnames  # the local it bound still has a slot

unguarded: dict = {}
exec(compile("def check(data):\n    return len(data)\n", "<example>", "exec"), unguarded)
assert unguarded["check"].__code__.co_nlocals < compiled[1].co_nlocals
```

## The Builtins Entry Is Not the Constant

`builtins.__debug__` tracks the flag at startup, and nothing reads it afterwards. Assigning to
it through `setattr()` is accepted and changes nothing that matters.

```python
import builtins

setattr(builtins, "__debug__", False)  # O(1) - an ordinary module attribute
try:
    assert getattr(builtins, "__debug__") is False

    namespace = {}
    exec(compile("value = __debug__", "<example>", "exec"), namespace)
    assert namespace["value"] is True  # the compiler does not consult it

    assert __debug__ is True  # and neither does code already compiled
finally:
    setattr(builtins, "__debug__", True)
```

## A Name That Cannot Be Bound

Every binding form is refused when the code is compiled, an attribute of another object
included. Reading such an attribute is fine; only binding one is not.

```python
for statement in ("__debug__ = False", "del __debug__", "x.__debug__ = False", "f(__debug__=1)"):
    try:
        compile(statement, "<example>", "exec")  # O(n) - and it never gets past the compiler
    except SyntaxError as error:
        assert "__debug__" in str(error)
    else:
        raise AssertionError(f"{statement!r} compiled")

assert compile("x.__debug__", "<example>", "eval")  # reading one is ordinary syntax

# Two of the six documented constants are ordinary builtins, and do rebind
namespace = {}
exec("NotImplemented = 67\nEllipsis = 68\nresult = (NotImplemented, Ellipsis)", namespace)
assert namespace["result"] == (67, 68)
```

## Common Patterns

### An Invariant That Costs Nothing in Production

```python
def merge(left, right):
    if __debug__:  # O(b) by default, dropped entirely under -O
        assert left == sorted(left), "left is not sorted"
        assert right == sorted(right), "right is not sorted"
    return sorted(left + right)

assert merge([1, 3], [2, 4]) == [1, 2, 3, 4]

try:
    merge([3, 1], [2])
except AssertionError as error:
    assert "left is not sorted" in str(error)
else:
    raise AssertionError("the invariant did not fire")
```

## Performance Best Practices

✅ **Do**:

- Put an expensive invariant behind `assert` or `if __debug__:`; under `-O` it costs nothing, not even its condition
- Read the bare name rather than `getattr(builtins, "__debug__")`, which is a lookup and can disagree with it
- Pass `optimize=` to `compile()` when you need a particular level, instead of re-running the interpreter

❌ **Avoid**:

- Validating untrusted input with `assert` - `-O` removes the check and its condition entirely
- Binding a name inside an assertion: `-O` drops the statement but not what it did to the function's names, so a later read raises `UnboundLocalError` or returns a different value
- Yielding inside an assertion: the function stays a generator under `-O` while the yield itself is gone
- `setattr(builtins, "__debug__", ...)` to force a mode: nothing reads the entry back
- Expecting `-O` to shrink a frame; the locals a dropped block bound keep their slots

## Version Notes

- **Python 3.14+**: `del x.__debug__` is a `SyntaxError`; 3.10 through 3.13 compile it, and it then deletes an attribute of that name like any other. Assigning to one has always been refused
- **Python 3.13+**: `ast.parse(source, optimize=1)` replaces the name with a `Constant` node
- **All Python 3**: `None`, `True`, `False` and `__debug__` are the four names that cannot be rebound; `Ellipsis` and `NotImplemented` are ordinary builtins that can be

## Related Functions

- **[Exceptions](exceptions.md)** - `AssertionError`, which a failed assertion raises
- **[compile()](compile.md)** - Where `optimize=` picks the level for one compilation
- **[ast](../stdlib/ast.md)** - `parse(optimize=)` applies the same substitution to a tree
- **[True](true.md)** and **[None](none.md)** - Constants the lexer resolves, rather than the compiler
