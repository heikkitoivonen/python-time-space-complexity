# __future__ Module Complexity

`__future__` is two things with one name. `from __future__ import feature` is a compiler
directive: it switches on a flag for the module being compiled, before any of that module runs.
`__future__` is also a small pure-Python module holding the feature table, one `_Feature` object
per feature, which a `from __future__ import` statement binds at run time like any other import.

On every supported version eight of the ten features are already part of the language, so
importing them changes nothing. `annotations` decides when annotation expressions are
evaluated, which is the one real cost this module controls. `a` is the annotations on one
function and `e` is the cost of evaluating their expressions; space bounds exclude whatever
those expressions allocate. The feature table is a fixed list of ten names, so every read of it
is O(1).

## Complexity Reference

### Future statements

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `from __future__ import feature` | O(1) | O(1) | Compile time: sets the feature's flag for this module. Only a docstring, comments, blank lines and other future statements may precede it. At run time it binds the `_Feature` object |
| `from __future__ import nested_scopes`, `generators`, `division`, `absolute_import`, `with_statement`, `print_function`, `unicode_literals`, `generator_stop` | O(1) | O(1) | Mandatory on every supported version: accepted, and changes nothing |
| `from __future__ import annotations` | O(1) | O(1) | Annotations compile to their source strings; no annotation expression runs when a function, class or module body is executed |
| An unknown feature, or a future statement after other code | O(1) | O(1) | `SyntaxError` when the module is compiled, not `ImportError` when it runs |

### Annotations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Defining an annotated function, with `annotations` | O(1) | O(1) | Nothing is evaluated or built until the first read |
| Defining an annotated function, without it, Python 3.10-3.13 | O(a + e) | O(a) | Every annotation expression is evaluated at definition |
| Defining an annotated function, without it, Python 3.14+ | O(1) | O(1) | Evaluation is deferred to the first `__annotations__` read |
| First `function.__annotations__` read | O(a) | O(a) | Plus e on 3.14+ without the import. The dictionary is cached, so later reads are O(1) |
| `typing.get_type_hints(function)` on string annotations | O(a + e) | O(a) | Evaluates every string again on each call; nothing is cached |

### Feature table

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `__future__.all_feature_names` | O(1) | O(1) | The list of all ten feature names, `barry_as_FLUFL` included |
| `__future__.nested_scopes`, `generators`, `division`, `absolute_import`, `with_statement`, `print_function`, `unicode_literals`, `generator_stop`, `annotations` | O(1) | O(1) | Module attributes, each a `_Feature` |

### _Feature

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `_Feature.optional`, `_Feature.getOptionalRelease()` | O(1) | O(1) | The release that first accepted the import, a 5-tuple shaped like `sys.version_info`; the method returns the attribute itself |
| `_Feature.mandatory`, `_Feature.getMandatoryRelease()` | O(1) | O(1) | The release the feature became the default, or `None` when that is undetermined, as it is for `annotations` on 3.11+ |
| `_Feature.compiler_flag` | O(1) | O(1) | The bit to pass as `compile(..., flags=...)` to turn the feature on in dynamically compiled code |

## Postponed Annotations

### When Annotation Expressions Run

Without the import, Python 3.10-3.13 evaluate every annotation when the `def` runs, and 3.14
defers that to the first read of `__annotations__`. Either way the evaluated dictionary is kept, so
the cost is paid once per function.

```python
import sys

calls = 0

def expensive():
    global calls
    calls += 1
    return int

def plain(x: expensive()) -> expensive():  # O(a + e) on 3.10-3.13, O(1) on 3.14+
    pass

if sys.version_info >= (3, 14):
    assert calls == 0
    assert plain.__annotations__ == {'x': int, 'return': int}  # O(a + e) on first read
assert calls == 2

assert plain.__annotations__ is plain.__annotations__  # O(1) - cached
assert calls == 2
```

With the import, nothing evaluates the expressions at all. They stay strings, so a name that does
not exist yet is no error, and reading `__annotations__` builds a dictionary of those strings.

```python
from __future__ import annotations

import __future__

assert annotations is __future__.annotations  # the statement also binds the name

calls = 0

def expensive():
    global calls
    calls += 1
    return int

def postponed(x: expensive(), y: Undefined) -> expensive():  # O(1)
    pass

class Point:
    x: expensive()

module_level: expensive()

assert postponed.__annotations__ == {  # O(a) on first read
    'x': 'expensive()', 'y': 'Undefined', 'return': 'expensive()'
}
assert Point.__annotations__ == {'x': 'expensive()'}
assert calls == 0
```

### Getting Real Types Back

`typing.get_type_hints()` turns the strings back into objects by evaluating each one. It keeps no
cache, so calling it on every use pays O(a + e) every time; keep its result instead.

```python
from __future__ import annotations

import typing

calls = 0

def expensive():
    global calls
    calls += 1
    return int

def f(x: expensive()):
    pass

hints = typing.get_type_hints(f)  # O(a + e)
assert hints == {'x': int}
assert calls == 1

typing.get_type_hints(f)  # O(a + e) again
assert calls == 2
```

## Future Flags in Dynamically Compiled Code

`compile()`, and `exec()` given a string, inherit the future flags of the code calling them. Pass
`dont_inherit=True` to stop that, and a feature's `compiler_flag` to switch it on explicitly.

```python
from __future__ import annotations

import __future__

source = "def f(x: Undefined): pass\n"
flag = __future__.annotations.compiler_flag  # O(1)

inherited = compile(source, "<dynamic>", "exec")  # inherits this module's flag
assert inherited.co_flags & flag

isolated = compile(source, "<dynamic>", "exec", dont_inherit=True)
assert not isolated.co_flags & flag

explicit = compile(source, "<dynamic>", "exec", flags=flag, dont_inherit=True)
namespace = {}
exec(explicit, namespace)
assert namespace['f'].__annotations__ == {'x': 'Undefined'}
```

## Placement and Unknown Features

A future statement is checked while the module is compiled. Anything but a docstring, comments
and other future statements before it is a `SyntaxError`, and so is a feature name the compiler does
not know. Neither ever gets as far as running an import.

```python
compile('"""Docstring."""\n# comment\nfrom __future__ import annotations\n', "<m>", "exec")

try:
    compile("import sys\nfrom __future__ import annotations\n", "<m>", "exec")
except SyntaxError as error:
    assert 'beginning of the file' in error.msg
else:
    raise AssertionError('a late future statement compiled')

try:
    compile("from __future__ import spam\n", "<m>", "exec")
except SyntaxError as error:
    assert 'spam is not defined' in error.msg
else:
    raise AssertionError('an unknown feature compiled')
```

## Common Patterns

### Which Features Still Do Something

A feature is part of the language once `mandatory` is a release at or before the running one.
Comparing the tuple with `sys.version_info` answers that for every feature on the running
interpreter.

```python
import sys
import __future__

names = __future__.all_feature_names  # O(1)
assert len(names) == 10

still_optional = [
    name for name in names
    if getattr(__future__, name).mandatory is None
    or getattr(__future__, name).mandatory > sys.version_info
]
assert still_optional == ['barry_as_FLUFL', 'annotations']

feature = __future__.division
assert feature.getOptionalRelease() is feature.optional  # O(1)
assert feature.getMandatoryRelease() == (3, 0, 0, 'alpha', 0)  # O(1)
```

## Performance Best Practices

✅ **Do**:

- Use `from __future__ import annotations` where annotations are costly to evaluate or name
  objects defined later: defining the function then evaluates nothing
- Call `typing.get_type_hints()` once and keep the result, since each call evaluates every
  annotation again
- Pass `dont_inherit=True` to `compile()` when dynamically compiled code must not pick up the
  caller's future flags

❌ **Avoid**:

- Adding future imports for features that are already mandatory - they change nothing
- Reading `__annotations__` expecting types under the import - they are strings, and turning them
  into types is a fresh O(a + e) evaluation

## Version Notes

- **Python 3.11+**: `annotations.getMandatoryRelease()` is `None`, as no release is set for it
  to become the default; on 3.10 it is `(3, 11, 0, 'alpha', 0)`
- **Python 3.14+**: Without the import, annotations are evaluated on the first `__annotations__`
  read rather than at definition; with it they are still strings

## Related Modules

- **[typing](typing.md)** - `get_type_hints()` evaluates postponed annotations
- **[annotationlib](annotationlib.md)** - Python 3.14's formats for reading deferred annotations
- **[inspect](inspect.md)** - `get_annotations()`, with `eval_str=True` to evaluate strings
- **[compile()](../builtins/compile.md)** - the `flags` and `dont_inherit` arguments
