# symtable Module Complexity

The `symtable` module exposes the symbol tables the compiler builds before it generates bytecode:
one table per module, class, function, lambda, generator expression and annotation or type
parameter scope, each recording how every name in that scope is bound and used. `symtable()`
parses and analyses the whole source at once; the Python objects that wrap the tables are then
made as you walk to them, and cache what they compute.

`n` is the characters of source. For the table a method is called on, `s` is the names in it and
`t` is its direct child tables. `b` is the blocks nested inside functions, and `f` is the names
bound by the functions enclosing such a block. Hashing a name and comparing two names are treated
as O(1).

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `symtable.symtable(code, filename, compile_type)` | O(n + b·f) | O(n) | Parses and analyses the whole source before returning, and raises `SyntaxError` for source it cannot parse. Every block nested in a function starts from a copy of the names its enclosing functions bind, which is the b·f term; `compile()` pays it too. Only the top table is wrapped here |
| `python -m symtable [file ...]` | O(n + b·f + Σ s·(1 + t)) | O(n) | Python 3.13+. Builds the table, then looks up every name of every table, as `get_symbols()` would; the sum runs over every table |

### SymbolTable

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SymbolTable.get_type()` | O(1) | O(1) | A string up to 3.12, a `SymbolTableType` member from 3.13 |
| `SymbolTable.get_id()`, `SymbolTable.get_name()`, `SymbolTable.get_lineno()` | O(1) | O(1) | The module's table is named `'top'` |
| `SymbolTable.is_optimized()`, `SymbolTable.is_nested()`, `SymbolTable.has_children()` | O(1) | O(1) | |
| `SymbolTable.get_identifiers()` | O(1) | O(1) | A view of the table's names, not a copy; iterating it is O(s) |
| `SymbolTable.lookup(name)` | O(t) first time, O(1) after | O(1) | The first lookup of a name scans every child table for ones bound to it, then caches the `Symbol` on this table object. `KeyError` for a name the table does not hold |
| `SymbolTable.get_symbols()` | O(s·(1 + t)) first time, O(s) after | O(s) | One `lookup()` per name, so a table with many functions is quadratic on the first call; later calls reuse the cached symbols in a new list |
| `SymbolTable.get_children()` | O(t) | O(t) | A new list on every call. A child keeps the same wrapper, and its caches, only while something still references it |

### Function

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Function.get_parameters()`, `Function.get_locals()`, `Function.get_globals()`, `Function.get_nonlocals()`, `Function.get_frees()` | O(s) first time, O(1) after | O(s) | Each filters the names once by their flags, with no scan of child tables, and returns the same cached tuple afterwards |

### Class

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Class.get_methods()` | O(t) first time, O(1) after | O(t) | Deprecated from 3.14, where every call warns |

### Symbol

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Symbol.get_name()` | O(1) | O(1) | |
| `Symbol.is_referenced()`, `Symbol.is_assigned()`, `Symbol.is_imported()`, `Symbol.is_annotated()`, `Symbol.is_parameter()` | O(1) | O(1) | Flag tests on an integer recorded when the table was built |
| `Symbol.is_global()`, `Symbol.is_declared_global()`, `Symbol.is_local()`, `Symbol.is_nonlocal()`, `Symbol.is_free()` | O(1) | O(1) | Scope tests on the same integer |
| `Symbol.is_type_parameter()`, `Symbol.is_free_class()`, `Symbol.is_comp_iter()`, `Symbol.is_comp_cell()` | O(1) | O(1) | Python 3.14+ |
| `Symbol.is_namespace()`, `Symbol.get_namespaces()` | O(1) | O(1) | The child tables bound to the name, found by the `lookup()` that made the symbol; the same list is returned every time |
| `Symbol.get_namespace()` | O(1) | O(1) | `ValueError` unless exactly one table is bound to the name |

### SymbolTableType

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `symtable.SymbolTableType.MODULE`, `FUNCTION`, `CLASS`, `ANNOTATION`, `TYPE_ALIAS`, `TYPE_PARAMETERS`, `TYPE_VARIABLE` | O(1) | O(1) | Python 3.13+. A `StrEnum`, so each member compares equal to its string value |

## Building a Symbol Table

`symtable()` does all of the compiler's analysis before it returns, so its cost is the source's,
not the part you go on to inspect. What it hands back is the module's table alone; child tables
get their Python wrappers when you reach them.

```python
import symtable

code = """
x = 10
def func(a, b):
    y = a + b
    return y
"""

table = symtable.symtable(code, '<string>', 'exec')  # O(n)
assert table.get_name() == 'top'   # O(1)
assert table.get_type() == 'module'  # O(1) - a str, or an equal SymbolTableType
assert table.has_children()          # O(1)

func = [c for c in table.get_children() if c.get_name() == 'func'][0]  # O(t)
assert func.get_type() == 'function'
assert func.is_optimized() and not func.is_nested()

try:
    symtable.symtable('def (:', '<string>', 'exec')
except SyntaxError:
    pass
else:
    raise AssertionError('invalid source produced a table')
```

### Names in Large Functions

Each block nested inside a function begins with a copy of every name its enclosing functions
bind. A function with f locals and b lambdas, comprehensions or inner functions therefore costs
O(b·f) to analyse, where the same statements at module level cost O(b + f). `compile()` does the
same analysis, so this is the price of the source, not of this module.

```python
import symtable

def lines(count):
    return ''.join(f'    x{i} = 1\n    g{i} = lambda: 0\n' for i in range(count))

nested = symtable.symtable('def outer():\n' + lines(100), '<string>', 'exec')  # O(n + b·f)
outer = nested.lookup('outer').get_namespace()
assert len(outer.get_locals()) == 200
```

## Looking Up Names

`lookup()` is a dictionary read plus, the first time a name is asked for, a scan of the table's
children for the ones bound to it. `get_symbols()` performs that lookup for every name, so on a
module that defines thousands of functions its first call is quadratic. Look up only the names
you need, and read a function's scopes through its `get_*()` methods, which filter the flags
directly.

```python
import symtable

code = "import os\nfrom sys import argv\ndef helper(): pass\ncount = 0\n"
table = symtable.symtable(code, '<string>', 'exec')

names = table.get_identifiers()  # O(1) - a view of the names
assert set(names) == {'os', 'argv', 'helper', 'count'}

sym = table.lookup('helper')  # O(t) the first time
assert table.lookup('helper') is sym  # O(1) - cached on the table object
assert sym.is_namespace() and sym.get_namespace().get_name() == 'helper'
assert table.lookup('os').is_imported()  # O(1)
assert table.lookup('count').is_assigned() and table.lookup('count').is_global()

symbols = table.get_symbols()  # O(s·(1 + t)) the first time
assert {s.get_name() for s in symbols} == set(names)

try:
    table.lookup('missing')
except KeyError:
    pass
else:
    raise AssertionError('an unknown name was found')

try:
    table.lookup('count').get_namespace()
except ValueError:
    pass
else:
    raise AssertionError('a plain variable had a namespace')
```

### Keeping Child Tables

The caches live on the wrapper objects. `get_children()` hands back the same wrapper for a child
only while something holds it, so a walk that drops the children and asks for them again starts
their lookups from scratch.

```python
import symtable

table = symtable.symtable("def f():\n    x = 1\n", '<string>', 'exec')

children = table.get_children()  # O(t) - keep the list to keep the caches
f = [c for c in children if c.get_name() == 'f'][0]
assert f.lookup('x') is f.lookup('x')
assert [c for c in table.get_children() if c.get_name() == 'f'][0] is f
```

## Function Scopes

A `Function` table answers scope questions from the flags it already holds. Each getter filters
the names once, O(s), and returns the same tuple on every later call.

```python
import symtable

code = """
counter = 0
def outer(step):
    total = 0
    def inner():
        nonlocal total
        global counter
        total += step
        counter += 1
    return inner
"""
table = symtable.symtable(code, '<string>', 'exec')
outer = table.lookup('outer').get_namespace()
inner = outer.lookup('inner').get_namespace()

assert outer.get_parameters() == ('step',)  # O(s) the first time
assert outer.get_parameters() is outer.get_parameters()  # O(1) - cached
assert set(outer.get_locals()) == {'step', 'total', 'inner'}
assert set(inner.get_frees()) == {'step', 'total'}
assert inner.get_nonlocals() == ('total',)
assert inner.get_globals() == ('counter',)
assert inner.is_nested()

assert inner.lookup('counter').is_declared_global()  # O(1)
assert inner.lookup('total').is_nonlocal() and inner.lookup('total').is_free()
assert outer.lookup('step').is_parameter() and inner.lookup('step').is_referenced()
```

## Common Patterns

### Finding Closures

A walk over every table costs the children it visits. Asking each function for its free
variables, rather than looking up every name, keeps each table at O(s + t).

```python
import symtable

code = """
def make(n):
    def add(x):
        return x + n
    return add

def plain(y):
    return y * 2
"""

def closures(table, found):
    if table.get_type() == 'function' and table.get_frees():  # O(s) once per table
        found.append((table.get_name(), table.get_frees()))
    for child in table.get_children():  # O(t)
        closures(child, found)
    return found

assert closures(symtable.symtable(code, '<string>', 'exec'), []) == [('add', ('n',))]
```

## Performance Best Practices

✅ **Do**:

- Use a function table's `get_locals()`, `get_frees()` and the other getters, which skip the
  child scan that `lookup()` pays per name
- `lookup()` the names you need instead of calling `get_symbols()` on a large module
- Keep the child tables you will revisit, so their cached symbols survive

❌ **Avoid**:

- `get_symbols()` on a module defining thousands of functions: its first call is O(s·(1 + t))
- Calling `get_children()` inside a loop and discarding the result each time

## Version Notes

- **Python 3.12+**: List, set and dict comprehensions have no table of their own; their names
  are the enclosing scope's. Generator expressions still get one. PEP 695 scopes appear as
  `'type parameter'`, `'type alias'` and `'TypeVar bound'` tables
- **Python 3.13+**: `get_type()` returns a `SymbolTableType` member, and the PEP 695 kinds are
  named `'type parameters'` and `'type variable'`. Added `python -m symtable`
- **Python 3.14+**: A `def` statement adds an `__annotate__` table of type `'annotation'` beside
  the function's own, and a body holding variable annotations adds one among its children. Added
  `is_type_parameter()`, `is_free_class()`, `is_comp_iter()` and `is_comp_cell()`; deprecated
  `Class.get_methods()`

## Related Modules

- **[ast](ast.md)** - the tree `symtable()` analyses; parsing it is the O(n) part
- **[dis](dis.md)** - the bytecode generated from these tables
- **[inspect](inspect.md)** - scopes of live objects rather than source
