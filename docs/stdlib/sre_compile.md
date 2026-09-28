# sre_compile Module Complexity

The `sre_compile` module turns a regular expression into the list of integer codes the C matcher
runs, and wraps that list in a `Pattern`. Given a string it parses it first with
[sre_parse](sre_parse.md); given a parse tree it compiles the tree as it is. On Python 3.10 it is
the compiler [re](re.md) itself imports. From Python 3.11 it is a deprecated alias: importing it
issues a `DeprecationWarning` and copies the names of the private `re._compiler` module. The
module has never been documented, so it carries no stability guarantee.

Nothing here is cached. `re.compile()` looks a pattern up in its cache before it compiles
anything; `sre_compile.compile()` parses and compiles on every call.

`n` is the characters in a pattern, `w` the items in a parse tree and `d` the depth to which its
groups and repeats nest, 1 when nothing nests (see [sre_parse](sre_parse.md)), `c` the codes in a compiled code list, and
`r` the code points the pattern's character-class ranges span below U+10000, summed over the
ranges.

## Complexity Reference

### Compiling

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import sre_compile` | O(1) | O(1) | Python 3.11+: warns on the first import only; the names are the same objects as `re._compiler`'s |
| `sre_compile.compile(p, flags=0)` | O(n + r) | O(n) | A string is parsed first, with the O(n²) and O(n·d) shapes of `sre_parse.parse()`; a tree from `parse()` costs O(w + r) and yields a `Pattern` whose `.pattern` is `None`. Groups nested d deep around a leading literal cost O(n·d), since each level copies the literal prefix. Each call returns a new `Pattern` |
| `sre_compile.isstring(obj)` | O(1) | O(1) | `True` for `str` and `bytes`, the two things `compile()` parses |
| `sre_compile.dis(code)` | O(c·d) | O(c) | Prints a code list, indenting each line by its depth, and keeps the set of jump targets it has seen; `compile()` calls it under `re.DEBUG` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_compile.MAXCODE` | O(1) | O(1) | The largest value one code can hold |
| `sre_compile.error`, `sre_compile.PatternError` | O(1) | O(1) | The class `re.error` names, raised for an invalid pattern; `PatternError` is Python 3.13+ |
| Opcode and flag constants | O(1) | O(1) | Re-exported from [sre_constants](sre_constants.md) |

## Importing a Deprecated Alias

From Python 3.11 the module's names are copied from `re._compiler` when it is first imported. They
are the same objects, but `re` looks them up in its own module, so rebinding one here changes
nothing `re` does. On Python 3.10 `re` calls through this module, and a rebinding reaches it.

```python
import re
import sys
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_compile

if sys.version_info >= (3, 11):
    import re._compiler
    assert sre_compile.compile is re._compiler.compile  # O(1) - the same function
else:
    assert re.sre_compile is sre_compile  # 3.10: the module re imports
```

## Compiling Without the Cache

Every call parses and compiles again. That is the difference from `re.compile()`, which returns
the cached `Pattern` for a string and flags it has seen before.

```python
import re
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_compile

first = sre_compile.compile(r'\d+')   # O(n)
second = sre_compile.compile(r'\d+')  # O(n) again - no cache
assert first is not second
assert first.match('42') and second.match('42')

assert re.compile(r'\d+') is re.compile(r'\d+')  # a cache hit returns the same object
```

### Compiling a Parse Tree

A tree from `sre_parse.parse()` compiles without being parsed again, and the same tree can be
compiled more than once. The resulting `Pattern` has no source string.

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_compile
    import sre_parse

tree = sre_parse.parse(r'(?P<year>\d{4})-(?P<month>\d\d)')  # O(n), once
pattern = sre_compile.compile(tree)  # O(w) - no second parse

assert pattern.pattern is None
assert pattern.groupindex == {'year': 1, 'month': 2}
assert pattern.match('2024-05').group('month') == '05'
assert sre_compile.compile(tree).match('1999-12')  # the tree is reusable
```

## Character-Class Ranges

A range inside a character class is expanded into a table one code point at a time, up to
U+FFFF. A five-character class such as `[\u4e00-\u9fff]` therefore costs its 20,992 code points,
not its five characters. Ranges above U+FFFF are kept as ranges.

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_compile

cjk = sre_compile.compile('[\u4e00-\u9fff]+')  # O(n + r), r = 20,992 code points
assert cjk.fullmatch('\u6f22\u5b57')

narrow = sre_compile.compile('[a-f]+')  # O(n + r), r = 6
assert narrow.fullmatch('cafe')

astral = sre_compile.compile('[\U00010000-\U0010ffff]')  # kept as one range
assert astral.match('\U0001f600')
```

## Performance Best Practices

✅ **Do**:

- Use `re.compile()` for matching: it caches, and it is the supported API
- Compile a tree from `sre_parse.parse()` directly when you already have one, rather than the
  string it came from

❌ **Avoid**:

- `sre_compile.compile()` in a loop over the same pattern - unlike `re.compile()`, it redoes all
  the work each time
- New code that imports the module on Python 3.11+ - it warns, and nothing in it is promised to
  stay
- Wide character-class ranges below U+10000 in a pattern compiled often; each range costs the code
  points it spans

## Version Notes

- **Python 3.11+**: A deprecated alias for `re._compiler`; importing it issues a
  `DeprecationWarning`, and `re` no longer imports it
- **Python 3.13+**: `PatternError` is the exception's name, with `error` kept as an alias
- **All Python 3**: Undocumented; the deprecation names no removal release

## Related Modules

- **[re](re.md)** - the public API, with the pattern cache this module does not have
- **[sre_parse](sre_parse.md)** - parses the string `compile()` is given
- **[sre_constants](sre_constants.md)** - the opcodes the code list is made of
