# pprint Module Complexity

The `pprint` module formats nested data - dicts, lists, tuples, sets and the `collections` types -
as text that fits a line width. It is pure Python and works top down: each object is first
rendered on one line, and only an object wider than the space left is broken into its items,
each of which is rendered on one line again.

`r` is the characters in the one-line representation (`saferepr(obj)`), `D` is the nesting depth
(1 for an object that holds nothing), `d` is the levels that are broken across lines (counted as
1 when everything fits), and `k` is the entries in one dict or set. `s` is the sorting work,
the sum of k·log k over the collections that get sorted: dicts when `sort_dicts=True` (the
default), sets that are broken across lines, and every `Counter`. Width and indent are treated as constants, and so is each key comparison. A leaf's
own `__repr__` is priced by the characters it returns.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pprint.pformat(object, indent=1, width=80, depth=None, *, compact=False, sort_dicts=True, underscore_numbers=False)` | O(d·(D·r + s)) | O(d·r) | Every level too wide for one line is rendered whole and then again item by item, and keeps its one-line string while its items are formatted |
| `pprint.pprint(object, stream=None, indent=1, width=80, depth=None, *, compact=False, sort_dicts=True, underscore_numbers=False)` | O(d·(D·r + s)) | O(d·r) | `pformat` written to `stream` (default `sys.stdout`); writing as it goes does not lower the peak |
| `pprint.pp(object, *args, sort_dicts=False, **kwargs)` | O(d·(D·r + s)) | O(d·r) | `pprint` with `sort_dicts=False`, so dicts drop out of s |
| `pprint.saferepr(object)` | O(D·r + s) | O(r) | One line, no width; each enclosing dict, list or tuple copies its items' text into its own string; dicts are always sorted; a reference cycle prints as `<Recursion on ...>` |
| `pprint.isreadable(object)`, `pprint.isrecursive(object)` | O(D·r + s) | O(r) | Build the whole `saferepr` string to return one flag; neither stops at the first unreadable or recursive item |

### PrettyPrinter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pprint.PrettyPrinter(indent=1, width=80, depth=None, stream=None, *, compact=False, sort_dicts=True, underscore_numbers=False)` | O(1) | O(1) | Stores settings; `stream=None` binds `sys.stdout` as it is at construction |
| `PrettyPrinter.pformat(object)`, `PrettyPrinter.pprint(object)` | O(d·(D·r + s)) | O(d·r) | As the functions, with this printer's settings |
| `PrettyPrinter.format(object, context, maxlevels, level)` | O(D·r + s) | O(r) | The one-line renderer every other call goes through; an override runs again for each enclosing level that is broken across lines |
| `PrettyPrinter.isreadable(object)`, `PrettyPrinter.isrecursive(object)` | O(D·r + s) | O(r) | As the functions, honouring this printer's `sort_dicts`; `depth` is ignored |

## Why Nesting Multiplies the Cost

`pformat()` renders an object on one line to see whether it fits. When it does not, it formats
each item in turn, and each item is rendered on one line again. A leaf nested d levels inside
containers that are all too wide is therefore rendered d + 1 times (`compact=True` adds one more
attempt per level), and every level keeps its one-line string alive while its items are
formatted. Flat data pays this once; a deep chain pays
it at every level.

```python
from pprint import pformat, saferepr

flat = list(range(1_000))
deep = flat
for _ in range(20):
    deep = [deep]

assert len(saferepr(deep)) == len(saferepr(flat)) + 40  # the same r
flat_text = pformat(flat)  # O(r) - D = d = 1
deep_text = pformat(deep)  # O(d·D·r) - 21 levels, each rendered whole
assert deep_text.count('\n') == flat_text.count('\n')  # the same lines, indented deeper
```

### When It All Fits

A wider line removes levels from d. Data that fits the width is rendered once and written as it
is, which makes `pformat()` cost what `saferepr()` does.

```python
from pprint import pformat, saferepr

data = {'users': [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]}

narrow = pformat(data, width=20)  # O(d·(D·r + s)) - three levels broken
wide = pformat(data, width=200)   # O(D·r + s) - one line
assert '\n' in narrow
assert wide == saferepr(data)
```

### Limiting Depth

`depth` replaces every dict, list and tuple below that level with `...`, so neither their one-line
strings nor anything beneath them is built. It is the one setting that shrinks r. Other containers,
sets included, are not cut, and the cut holds only where the shortened line fits the width: a level
that is still too wide is broken and its items formatted in full.

```python
from pprint import pformat

data = {'a': {'b': {'c': list(range(1_000))}}}

assert pformat(data, depth=2) == "{'a': {'b': {...}}}"  # the list is never visited
assert pformat([[[[1]]]], depth=2) == '[[[...]]]'
assert pformat([[1, 2], [3, 4]], depth=1, width=5) == '[[1,\n  2],\n [3,\n  4]]'  # too narrow to cut
```

## Sorting

`sort_dicts=True` sorts each dict's keys, O(k log k), every time the dict is rendered: on one line
once for itself and once per level above it that is broken across lines, and once more if the
dict itself is broken.
`sort_dicts=False` and `pp()` keep insertion order and skip the sort. Sets are sorted when they are
broken across lines, whatever `sort_dicts` says.

```python
import io
from pprint import pformat, pp

data = {'b': 1, 'a': 2}

assert pformat(data) == "{'a': 2, 'b': 1}"                    # O(k log k) sort
assert pformat(data, sort_dicts=False) == "{'b': 1, 'a': 2}"  # insertion order

out = io.StringIO()
pp(data, stream=out)  # sort_dicts=False by default
assert out.getvalue() == "{'b': 1, 'a': 2}\n"
```

## Safe Representations

`saferepr()` is the one-line renderer without the width: one pass, O(D·r + s). It sorts dict keys
and marks a reference cycle as `<Recursion on ...>` where `repr()` writes `{...}`.
`isreadable()` and `isrecursive()` build the same string and return one of its flags.

```python
from pprint import isreadable, isrecursive, saferepr

data = {'a': 1}
data['self'] = data  # a reference cycle

text = saferepr(data)  # O(D·r + s)
assert text.startswith("{'a': 1, 'self': <Recursion on dict with id=")
assert repr(data) == "{'a': 1, 'self': {...}}"

assert isrecursive(data) is True     # O(D·r + s) - the whole string is built
assert isreadable(data) is False     # a cycle cannot round-trip through eval()
assert isreadable({'a': [1, 2]}) is True
assert isreadable(object()) is False  # '<object object at ...>'
```

### Deep Nesting

`pprint` recurses in Python, two or more frames for every level of nesting, so a structure nested
a few hundred levels deep raises `RecursionError` under the default recursion limit. `repr()`
handles the same structure.

```python
import sys
from pprint import pformat, saferepr

deep = []
for _ in range(sys.getrecursionlimit() // 2):
    deep = [deep]

assert repr(deep).startswith('[[[')
for render in (saferepr, pformat):
    try:
        render(deep)
    except RecursionError:
        pass
    else:
        raise AssertionError(f'{render.__name__} rendered {len(repr(deep)) // 2} levels')
```

## Customising a Printer

A `PrettyPrinter` holds only its settings, so building one is O(1) and it can be reused. The
settings change the layout, not the bound: `compact=True` packs several items on a line, `indent`
widens each level, and `underscore_numbers=True` groups the digits of ints.

```python
import io
from pprint import PrettyPrinter

out = io.StringIO()
printer = PrettyPrinter(width=40, compact=True, stream=out)  # O(1)

printer.pprint(list(range(30)))  # O(r) - one level to break
assert out.getvalue().count('\n') == 3

assert PrettyPrinter(underscore_numbers=True).pformat(10**9) == '1_000_000_000'
assert PrettyPrinter(indent=4, width=5).pformat([1, 2]) == '[   1,\n    2]'
```

### Overriding format()

Every one-line rendering goes through `PrettyPrinter.format()`, so a subclass can change how
leaves are shown. It runs again for every enclosing level that is broken across lines, so an
expensive override is paid again at every broken level.

```python
from pprint import PrettyPrinter

class HideSecrets(PrettyPrinter):
    calls = 0

    def format(self, object, context, maxlevels, level):
        if isinstance(object, str) and object.startswith('sk-'):
            HideSecrets.calls += 1
            return "'***'", True, False
        return super().format(object, context, maxlevels, level)

printer = HideSecrets(width=30)
text = printer.pformat({'user': 'alice', 'token': ['sk-123', 'sk-456']})
assert "sk-" not in text and "'***'" in text
assert HideSecrets.calls > 2  # each secret was rendered at more than one level
```

## Common Patterns

### Formatting for a Log

`pformat()` runs when it is called, whether or not the log record is emitted. Guard it, so a
disabled debug level costs nothing.

```python
import logging
from pprint import pformat

logger = logging.getLogger('example')
logger.setLevel(logging.INFO)

calls = 0

def expensive():
    global calls
    calls += 1
    return {'rows': list(range(1_000))}

if logger.isEnabledFor(logging.DEBUG):  # O(1)
    logger.debug('state:\n%s', pformat(expensive()))  # O(d·(D·r + s)), skipped here

assert calls == 0
```

## Performance Best Practices

✅ **Do**:

- Pass `depth=` for large or deep data: it is the only setting that stops `pprint` visiting what
  it elides
- Widen `width` when the output does not need to wrap; every level that fits is rendered once
- Use `sort_dicts=False` (or `pp()`) when insertion order is fine; it removes the per-level dict
  sort

❌ **Avoid**:

- Pretty-printing deep chains of wide containers: each broken level renders its whole subtree
  again and keeps that string alive
- Calling `pformat()` for a log message that may not be emitted
- Using `pprint` on data nested hundreds of levels deep; it raises `RecursionError` where `repr()`
  does not
- Using `isrecursive()` as a quick check: it renders the whole object first

## Version Notes

- **Python 3.11+**: `pprint()` writes nothing when `sys.stdout` is `None`, instead of raising

## Related Modules

- **[reprlib](reprlib.md)** - a size-limited `repr()` that cuts long containers, where `pprint`
  lays them out in full
- **[json](json.md)** - `json.dumps(obj, indent=...)` is a single pass for JSON-compatible data
