# pyclbr Module Complexity

The `pyclbr` module reads a Python source file and describes the classes and functions it
defines, without importing or executing it. Each read parses the whole file into an abstract
syntax tree, walks it once, and keeps a `Class` or `Function` for each name defined; the tree
itself is dropped. A name defined twice in the same scope keeps its later definition.

`s` is the source characters read: the module asked for, plus every module it reaches through
top-level imports that has not been read before in the process. A `from module import *` copies
that module's public entries, which s counts as though they were read again. `t` is the
top-level entries in one module's result. Locating a module on the search path is filesystem
work outside these bounds.

## Complexity Reference

### Reading a module

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pyclbr.readmodule_ex(module, path=None)` | O(s) | O(s) | Parses without executing; `path` is searched before `sys.path`, but a module already imported is read from the file it was imported from. The syntax tree is dropped after the read. A package's result also has a `'__path__'` entry |
| Repeating `readmodule_ex()` for a module already read | O(1) | O(1) | Results are cached by module name for the life of the process and returned as the same dict, even after the file changes or with a different `path` |
| `pyclbr.readmodule(module, path=None)` | O(s) | O(s) | The same read and cache, then a new dict of just the top-level classes; a repeat call is O(t) |
| Top-level imports in the module read | Included in s | Included in s | An absolute `import` or `from ... import` at column 0 reads the named module too, transitively; imports nested in a `def`, `class`, `if` or `try` are not followed |
| A dotted name, `readmodule_ex('pkg.mod')` | O(s) | O(s) | Reads the package first; its source is part of s |
| A builtin module, or one with no Python source to read | O(1) | O(1) | An empty dict, or just `'__path__'` for a package: an extension module has no source, and from Python 3.11 neither do the standard modules the interpreter runs frozen, such as `os` |

### Class

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pyclbr.Class` | O(1) | O(1) | One per `class` statement, built by the reader |
| `Class.name`, `Class.module`, `Class.file`, `Class.lineno`, `Class.end_lineno` | O(1) | O(1) | Stored values |
| `Class.parent` | O(1) | O(1) | The enclosing `Class` or `Function`, `None` at top level |
| `Class.super` | O(1) | O(1) | A list built at read time: a base the reader resolved is the object it resolved to, normally a `Class`; a plain name it could not resolve stays a string |
| `Class.methods` | O(1) | O(1) | Dict of method name to line number; functions defined inside a method are not included |
| `Class.children` | O(1) | O(1) | Dict of the classes and functions defined one level down, by name |

### Function

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pyclbr.Function` | O(1) | O(1) | One per `def` or `async def` statement, methods included, built by the reader |
| `Function.name`, `Function.module`, `Function.file`, `Function.lineno`, `Function.end_lineno` | O(1) | O(1) | Stored values |
| `Function.parent` | O(1) | O(1) | The enclosing `Class` or `Function`, `None` at top level |
| `Function.is_async` | O(1) | O(1) | `True` for `async def` |
| `Function.children` | O(1) | O(1) | Dict of the classes and functions defined one level down, by name |

## Reading Without Importing

`readmodule_ex()` parses the source, so a module whose top level would fail, block or have side
effects is described without any of that happening. The cost is the parse: O(s) in the size of
the source, whatever the module would have done when run.

```python
import os
import pyclbr
import sys
import tempfile

source = '''
raise SystemExit('importing this module exits')

class Shape:
    def area(self):
        return 0

async def fetch():
    pass
'''

with tempfile.TemporaryDirectory() as directory:
    with open(os.path.join(directory, 'shapes.py'), 'w') as f:
        f.write(source)

    tree = pyclbr.readmodule_ex('shapes', [directory])  # O(s) - parsed, not executed

assert 'shapes' not in sys.modules
assert sorted(tree) == ['Shape', 'fetch']
assert isinstance(tree['Shape'], pyclbr.Class)
assert tree['Shape'].methods == {'area': 5}  # O(1)
assert tree['fetch'].is_async                # O(1)

# readmodule keeps only the classes
assert list(pyclbr.readmodule('shapes')) == ['Shape']  # O(t) - the read is cached
```

## The Module Cache

Every module read is cached by its name for the rest of the process, and a repeat call returns
the cached dict itself. That makes a second call O(1), and it also means the result does not
follow the file: an edit to it, or a different `path` that would find another file of the same
name, is not seen. There is no function to clear the cache; `importlib.reload(pyclbr)` starts an
empty one.

```python
import os
import pyclbr
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'cached.py')
    with open(path, 'w') as f:
        f.write('class First:\n    pass\n')

    first = pyclbr.readmodule_ex('cached', [directory])  # O(s)

    with open(path, 'a') as f:
        f.write('class Second:\n    pass\n')

    again = pyclbr.readmodule_ex('cached', [directory])  # O(1) - the cached dict

assert again is first
assert list(again) == ['First']  # the edit is not seen
```

## Imports Are Followed

An import at column 0 is read as well, so that a base class or a name bound by `from ... import`
can be resolved to a `Class`. That reads the imported module, then what it imports, so s is the
source of everything the module reaches that was not read before, not just the file asked for.
Imports indented under a `def`, `class`, `if` or `try` are skipped, and so is a module that
cannot be found.

```python
import os
import pyclbr
import tempfile

files = {
    'base.py': 'class Base:\n    pass\n',
    'extra.py': 'class Extra:\n    pass\n',
    'app.py': (
        'from base import Base\n'
        'if True:\n'
        '    from extra import Extra\n'
        'import missing_module\n'
        'class App(Base):\n'
        '    pass\n'
    ),
}

with tempfile.TemporaryDirectory() as directory:
    for name, text in files.items():
        with open(os.path.join(directory, name), 'w') as f:
            f.write(text)

    tree = pyclbr.readmodule_ex('app', [directory])  # O(s) - app.py and base.py

assert sorted(tree) == ['App', 'Base']  # Base came from base.py; Extra was not read
assert tree['App'].super == [tree['Base']]
assert tree['Base'].module == 'base'
```

## Classes, Methods and Nesting

A `Class` or `Function` holds what the reader recorded: its location, its parent, and dicts of
what is nested directly inside it. Reading any of them is O(1).

```python
import os
import pyclbr
import tempfile

source = '''\
class Node(Unknown):
    def walk(self):
        def visit(child):
            pass

    class Meta:
        pass

class Leaf(Node):
    pass
'''

with tempfile.TemporaryDirectory() as directory:
    with open(os.path.join(directory, 'nodes.py'), 'w') as f:
        f.write(source)

    tree = pyclbr.readmodule_ex('nodes', [directory])  # O(s)

node = tree['Node']
assert node.super == ['Unknown']            # unresolved base: its name as a string
assert tree['Leaf'].super == [node]         # resolved base: the Class itself
assert node.methods == {'walk': 2}          # direct defs only
assert sorted(node.children) == ['Meta', 'walk']
assert node.children['walk'].children['visit'].parent is node.children['walk']
assert (node.lineno, node.end_lineno) == (1, 7)
assert node.parent is None and node.file.endswith('nodes.py')
```

## Common Patterns

### Listing Every Definition

`children` links the result into a tree, so one walk lists every class and function, nested ones
included. A package's result also holds `'__path__'`, which the walk skips.

```python
import os
import pyclbr
import tempfile

source = '''\
class Outer:
    def method(self):
        pass
    class Inner:
        def deep(self):
            pass

def helper():
    pass
'''

with tempfile.TemporaryDirectory() as directory:
    with open(os.path.join(directory, 'layout.py'), 'w') as f:
        f.write(source)

    tree = pyclbr.readmodule_ex('layout', [directory])  # O(s)

def walk(objects, prefix=''):
    found = [
        (name, obj) for name, obj in objects.items()
        if isinstance(obj, (pyclbr.Class, pyclbr.Function))
    ]
    for name, obj in sorted(found, key=lambda item: item[1].lineno):  # in line order
        yield prefix + name, obj.lineno
        yield from walk(obj.children, prefix + name + '.')

assert list(walk(tree)) == [
    ('Outer', 1),
    ('Outer.method', 2),
    ('Outer.Inner', 4),
    ('Outer.Inner.deep', 5),
    ('helper', 8),
]
```

## Performance Best Practices

✅ **Do**:

- Use `pyclbr` to describe a module you do not want to run: the cost is a parse, not an import
- Re-read a module freely within one process; after the first read each call is an O(1) cache hit
- Expect a module with many top-level imports to cost the source it reaches, not only its own

❌ **Avoid**:

- Relying on `pyclbr` to see an edited file in the same process; the first result is cached for
  good
- Reading two different files with the same module name through different `path` values; the
  second call returns the first file's result
- `readmodule()` in a loop over the same module when `readmodule_ex()` would do: it builds a new
  O(t) dict each time

## Version Notes

- **Python 3.11+**: `os`, `io`, `codecs` and the other modules the interpreter freezes at startup
  have no source for `pyclbr` to read, so `readmodule_ex('os')` is an empty dict unless the
  interpreter runs with `-X frozen_modules=off`

## Related Modules

- **[ast](ast.md)** - the parser `pyclbr` runs; use it directly for anything beyond classes and
  functions
- **[inspect](inspect.md)** - describes objects after importing them, which runs the module
- **[importlib](importlib.md)** - how a module name is found on the search path
