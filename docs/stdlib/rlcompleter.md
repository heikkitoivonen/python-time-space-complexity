# rlcompleter Module Complexity

The `rlcompleter` module completes Python names and attributes for `readline`'s Tab key. A
`Completer` keeps a reference to one namespace dictionary. The first call for a word builds the
whole match list and keeps it; readline then asks for the matches one at a time, and each of
those calls is an index into the stored list.

`n` is the names in the namespace plus the names in `builtins`, `m` is the matches returned, `a`
is the most names any single `dir()` call returns while completing an attribute, and `d` is the
classes the walk over `__bases__` visits, counted once per path to each. The bounds treat the
typed text as short, so comparing a name with it is O(1), and count the `getattr()` and, for a
callable, the `inspect.signature()` that each match pays as O(1). Evaluating the dotted prefix
of an attribute completion is priced separately: it runs whatever properties and
`__getattr__` hooks the objects on the way define.

## Complexity Reference

### Completer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `rlcompleter.Completer(namespace=None)` | O(1) | O(1) | Keeps a reference to the dictionary, not a copy; with no namespace, `__main__.__dict__` is read at each completion |
| `Completer.complete(text, 0)` for a plain name | O(n) | O(m) | Runs `global_matches()` and keeps the list. Whitespace-only text completes to a tab and searches nothing |
| `Completer.complete(text, 0)` for a dotted name | O(d·a·(d + log a)) | O(d·a) | Runs `attr_matches()` and keeps the list |
| `Completer.complete(text, state)` with `state > 0` | O(1) | O(1) | Indexes the list the `state == 0` call kept; `None` past its end |
| `Completer.global_matches(text)` | O(n) | O(m) | Keywords, then the namespace, then `builtins`; a namespace name hides a builtin of the same name |
| `Completer.attr_matches(text)` | O(d·a·(d + log a)) | O(d·a) | Plus evaluating the prefix. O(a log a) for a module or a shallow class. Returns `[]` when the prefix raises; a property on the last object is not called |

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `rlcompleter.get_class_members(klass)` | O(d·a·(d + log a)) | O(d·a) | `dir()` of the class and of every base reached through `__bases__`, repeats kept; a base is walked once per path to it |
| `import rlcompleter` | O(1) | O(1) | When `readline` imports, installs a new `Completer().complete` as its completer, replacing any set before |

## Completing Names

readline calls `complete()` with `state` 0, 1, 2, ... until it returns `None`. The `state == 0`
call scans the namespace, `builtins` and the keywords once and keeps the list, so a whole
completion is one O(n) scan plus m + 1 O(1) calls. A callable match ends in `(`, or in `()`
when `inspect.signature()` reports no parameters.

```python
import rlcompleter

namespace = {'apple': 1, 'apricot': 2, 'apply_all': len, 'apron': lambda: None}
completer = rlcompleter.Completer(namespace)  # O(1)

results = []
state = 0
while (result := completer.complete('ap', state)) is not None:  # O(n) once, then O(1)
    results.append(result)
    state += 1
assert results == ['apple', 'apricot', 'apply_all(', 'apron()']

assert completer.complete('whi', 0) == 'while '  # keywords are completed too
assert completer.complete('isinst', 0) == 'isinstance('  # and builtins
assert completer.complete('zzz', 0) is None
```

### Choosing the Namespace

The namespace is held by reference, so names added after the `Completer` is built are found.
Without one, the completer reads `__main__.__dict__` at every completion, which is what the
interactive interpreter wants.

```python
import rlcompleter

namespace = {}
completer = rlcompleter.Completer(namespace)  # O(1) - no copy
namespace['late_arrival'] = 1
assert completer.complete('late', 0) == 'late_arrival'

try:
    rlcompleter.Completer({'a': 1}.items())
except TypeError as error:
    assert 'dictionary' in str(error)
else:
    raise AssertionError('a non-dict namespace was accepted')
```

## Completing Attributes

A dotted name is evaluated up to its last dot in the namespace, so every property and
`__getattr__` along the way runs, once per completion. The object that is left is listed with
`dir()`, together with `dir()` of its class and of each base, and the matches are sorted. A
property on that last object is not called. An exception from the prefix is swallowed and the
completion is empty.

```python
import rlcompleter

calls = []

class Node:
    @property
    def child(self):
        calls.append('child')
        return Node()

    def visit(self, other):
        return other

namespace = {'node': Node()}
completer = rlcompleter.Completer(namespace)

assert completer.complete('node.ch', 0) == 'node.child'  # the property is not called
assert calls == []

assert completer.complete('node.child.vi', 0) == 'node.child.visit('
assert calls == ['child']  # evaluating the prefix called it once

assert completer.complete('missing.attr', 0) is None  # NameError is swallowed
```

### Deep Hierarchies

The walk over `__bases__` calls `dir()` on every class it reaches, keeps the repeats and
concatenates the lists level by level. Along a single chain of classes, cost grows with the
square of its length; a base reached through two parents is walked twice.

```python
import rlcompleter

class Base:
    only_on_base = 1

class Left(Base):
    pass

class Right(Base):
    pass

class Diamond(Left, Right):
    pass

names = rlcompleter.get_class_members(Diamond)  # O(d·a·(d + log a))
# Listed by dir() of Diamond, Left, Base, Right and Base again
assert names.count('only_on_base') == 5
```

## Setting Up Tab Completion

Importing the module installs a `Completer` over `__main__` as readline's completer, replacing
whatever was set before. Set your own afterwards to complete from another namespace. The binding
that turns Tab into completion is spelled differently for GNU readline and libedit.

```python
import readline
import rlcompleter

completer = rlcompleter.Completer({'answer': 42})  # O(1)
readline.set_completer(completer.complete)
assert readline.get_completer() == completer.complete

if 'libedit' in readline.__doc__:
    readline.parse_and_bind('bind ^I rl_complete')
else:
    readline.parse_and_bind('tab: complete')
```

## Performance Best Practices

✅ **Do**:

- Override `global_matches()` or `attr_matches()` to change what is offered: they run once per
  completion, while `complete()` runs m + 1 times
- Pass a small namespace dictionary when completing outside the interpreter, so the scan is
  over the names you mean

❌ **Avoid**:

- Slow or side-effecting properties and `__getattr__` hooks on objects you complete through:
  each completion of a deeper attribute runs them again
- Rebuilding the match list in a `complete()` override on every `state`; that turns one O(n)
  scan into m + 1 of them

## Version Notes

- **Python 3.11+**: Soft keywords from `keyword.softkwlist`, such as `match` and `case`, are
  completed as well

## Related Modules

- **[readline](readline.md)** - the line editor that calls the completer, and the Tab binding
- **[keyword](keyword.md)** - the keyword lists that plain-name completion offers
- **[site](site.md)** - imports this module for the interactive interpreter
