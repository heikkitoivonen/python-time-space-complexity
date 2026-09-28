# sre_parse Module Complexity

The `sre_parse` module turns a regular-expression string into the intermediate tree that
[sre_compile](sre_compile.md) translates into matcher code. On Python 3.10 it is the parser
[re](re.md) itself imports. From Python 3.11 it is a deprecated alias: importing it issues a
`DeprecationWarning` and copies the names of the private `re._parser` module, which is what `re`
uses. The module has never been documented, so it carries no stability guarantee - signatures and
return shapes change between releases (see [Version Notes](#version-notes)). For the cost of
compiling and matching through the public API, see [re](re.md).

`n` is the characters in a pattern, `t` the characters in a replacement template, `r` the
characters in an expanded replacement, `w` the items in a parse tree (each literal, repeat, group,
anchor and character-class member is one item, nested trees included), `d` the depth to which
groups and repeats nest (1 when nothing nests), and `k` the characters one tokenizer call takes. Dictionary lookups are
O(1).

## Complexity Reference

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import sre_parse` | O(1) | O(1) | Python 3.11+: warns on the first import only; the names are the same objects as `re._parser`'s |
| `sre_parse.parse(str, flags=0, state=None)` | O(n) | O(n) | O(n²) when a group's alternatives share a long common prefix, or when a long run of non-capturing groups such as `(?:ab)(?:cd)` sits at one level; O(n·d) when non-capturing groups nest d deep, since each level copies what it holds. Returns a `SubPattern`; nothing is cached |
| `sre_parse.fix_flags(src, flags)` | O(1) | O(1) | Adds `SRE_FLAG_UNICODE` for a `str` pattern without `ASCII`; raises `ValueError` for flags the pattern type cannot take |
| `sre_parse.parse_template(source, pattern)` | O(t) | O(t) | `pattern` is a compiled `Pattern`. Python 3.12+ returns a list alternating literals and group numbers; 3.10-3.11 name the argument `state` and return a `(groups, literals)` pair |
| `sre_parse.expand_template(template, match)` | O(t + r) | O(t + r) | Python 3.10-3.11 only; fills a `parse_template()` result from a match |

### State

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_parse.State()` | O(1) | O(1) | The group bookkeeping for one parse; `parse()` makes one when `state` is omitted |
| `State.groups` | O(1) | O(1) | Groups opened so far, counting group 0 |
| `State.flags`, `State.groupdict` | O(1) | O(1) | The pattern's flags and its name-to-number map, filled in as the parse goes |
| `State.opengroup(name=None)` | O(1) | O(1) | Raises `error` for a repeated name or past `MAXGROUPS` |
| `State.closegroup(gid, p)` | O(w) | O(w) | Records `p.getwidth()`, which walks the group's tree unless it has been asked before |
| `State.checkgroup(gid)`, `State.checklookbehindgroup(gid, source)` | O(1) | O(1) | Validate a backreference while parsing; a rejected reference in a lookbehind costs what `Tokenizer.error()` does |

### SubPattern

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_parse.SubPattern(state, data=None)` | O(1) | O(1) | Wraps a list of `(opcode, argument)` items without copying it |
| `SubPattern.data`, `SubPattern.state` | O(1) | O(1) | The item list and the `State` it belongs to |
| `len(sub)`, `sub[i]`, `SubPattern.append(code)` | O(1) | O(1) | `append` is amortized O(1) |
| `sub[i:j]` | O(j - i) | O(j - i) | A new `SubPattern` over a copied slice |
| `SubPattern.insert(index, code)`, `del sub[i]` | O(w) | O(1) | Shift the items after `index` |
| `SubPattern.getwidth()` | O(w) | O(w) | The `(min, max)` length a match can have, stored on every nested `SubPattern` it visits. Stored on the first call and returned from then on, so an item added afterwards is not counted |
| `SubPattern.dump(level=0)` | O(w·d) | O(d) | Prints the tree, indenting each line by its depth; `re.DEBUG` prints the same thing |

### Tokenizer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_parse.Tokenizer(string)` | O(1) for `str`, O(n) for `bytes` | O(1) for `str`, O(n) for `bytes` | A `bytes` pattern is decoded as Latin-1 once, up front |
| `Tokenizer.get()`, `Tokenizer.match(char)`, `Tokenizer.next` | O(1) | O(1) | One character, or one backslash escape, at a time |
| `Tokenizer.tell()`, `Tokenizer.pos`, `Tokenizer.seek(index)` | O(1) | O(1) | Positions are indexes into the pattern |
| `Tokenizer.getwhile(n, charset)`, `Tokenizer.getuntil(terminator, name)` | O(k) | O(k) | `getwhile` stops after its `n` argument's worth of characters from `charset` |
| `Tokenizer.checkgroupname(name, offset)` | O(k) | O(k) | Python 3.11+; on 3.11 alone it takes a third `nested` argument. Raises `error` unless `name` is an identifier, which adds the cost of `error()` |
| `Tokenizer.error(msg, offset=0)` | O(n) | O(1) | Returns an `error` located at the current position, without raising it; finding its line and column scans the pattern up to there. The bound treats `msg` as short |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_parse.SPECIAL_CHARS`, `sre_parse.REPEAT_CHARS` | O(1) | O(1) | Strings of the metacharacters and of the repeat characters |
| `sre_parse.DIGITS`, `sre_parse.OCTDIGITS`, `sre_parse.HEXDIGITS`, `sre_parse.ASCIILETTERS`, `sre_parse.WHITESPACE` | O(1) | O(1) | Frozensets, so a membership test is O(1) |
| `sre_parse.ESCAPES`, `sre_parse.CATEGORIES` | O(1) | O(1) | Dicts from an escape such as `\n` or `\d` to its parse-tree item |
| `sre_parse.FLAGS`, `sre_parse.TYPE_FLAGS`, `sre_parse.GLOBAL_FLAGS` | O(1) | O(1) | Inline flag letters and the flag groups they are checked against |
| `sre_parse.MAXWIDTH` | O(1) | O(1) | Python 3.11+; the cap on the widths `getwidth()` reports |
| `sre_parse.Verbose` | O(1) | O(1) | Python 3.10 only; raised internally to restart the parse when `(?x)` turns up |
| `sre_parse.error`, `sre_parse.PatternError` | O(1) | O(1) | The class `re.error` names; `PatternError` is Python 3.13+ |
| Opcode and flag constants | O(1) | O(1) | Re-exported from [sre_constants](sre_constants.md) |

## Importing a Deprecated Alias

On Python 3.11+ the module is a thin copy of `re._parser`, so everything it holds is the object
`re` uses. The warning fires once per process, on the import that loads the module; later imports
find it in `sys.modules` and stay silent.

```python
import sys
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter('always')
    import sre_parse  # O(1)

if sys.version_info >= (3, 11):
    import re._parser
    assert [w.category for w in caught] == [DeprecationWarning]
    assert sre_parse.parse is re._parser.parse  # the same function, not a copy
else:
    assert caught == []  # 3.10: the real parser, which does not warn
```

## Parsing a Pattern

`parse()` returns a `SubPattern`: a list of `(opcode, argument)` items, with nested groups and
repeats holding their own `SubPattern`. Each call parses from scratch.

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_constants
    import sre_parse

tree = sre_parse.parse(r'(?P<word>\w{1,4})-\d{2,4}')  # O(n)

assert len(tree) == 3  # the group, the literal '-', the repeat
assert tree[0][0] is sre_constants.SUBPATTERN
assert tree[1] == (sre_constants.LITERAL, ord('-'))
assert tree.state.groupdict == {'word': 1}

width = tree.getwidth()  # O(w) once, then O(1)
assert width == (4, 9)  # the shortest and the longest match
assert tree.getwidth() is width  # stored, not recomputed
```

### Where Parsing Goes Quadratic

Two shapes cost more than their length: alternatives that share a prefix, which is moved out of
the branch one item at a time, and a run of non-capturing groups side by side, each spliced into
the list that holds it. Both are O(n²) only when the shared prefix or the run of groups is long.
Non-capturing groups nested inside each other are spliced once per level, so their contents are
copied d times.

```python
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_constants
    import sre_parse

LITERAL = sre_constants.LITERAL

# The shared 'ab' leaves the branch; what is left is a class of two characters
tree = sre_parse.parse('abc|abd')  # O(n) here; O(n²) for a long shared prefix
assert tree[0] == (LITERAL, ord('a')) and tree[1] == (LITERAL, ord('b'))
assert tree[2][0] is sre_constants.IN

# Non-capturing groups disappear into the list that holds them
flat = sre_parse.parse('(?:ab)(?:cd)')  # O(n) here; O(n²) for a long run of groups
assert [item[1] for item in flat] == [ord(c) for c in 'abcd']
```

## Replacement Templates

`parse_template()` splits a replacement string such as `r'\2-\1'` into literal text and group
references once, so each substitution only joins pieces. Its result changed shape in Python 3.12.

```python
import re
import sys
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_parse

pattern = re.compile(r'(\w+) (\w+)')
template = sre_parse.parse_template(r'\2-\1', pattern)  # O(t)

if sys.version_info >= (3, 12):
    assert template == ['', 2, '-', 1, '']  # literals and group numbers, alternating
else:
    groups, literals = template
    assert groups == [(0, 2), (2, 1)] and literals == [None, '-', None]
    match = pattern.match('hello world')
    assert sre_parse.expand_template(template, match) == 'world-hello'  # O(t + r)
```

## Performance Best Practices

✅ **Do**:

- Use `re.compile()` for matching: it caches, and it is the supported API
- Parse once and hand the tree to `sre_compile.compile()` when a tool needs both the tree and a
  compiled pattern, rather than parsing the string twice

❌ **Avoid**:

- New code that imports the module on Python 3.11+ - it warns, and the tree it returns is an
  internal format with no compatibility promise
- Rebinding a name in the module to intercept `re` - from Python 3.11 `re` never looks there
- A long alternation whose alternatives share a long prefix, or a long run of `(?:...)` groups
  side by side - both parse in O(n²)
- Wrapping a long pattern in many layers of `(?:...)` - each layer copies it again

## Version Notes

- **Python 3.11+**: A deprecated alias for `re._parser`; importing it issues a `DeprecationWarning`,
  and `re` no longer imports it
- **Python 3.12+**: `parse_template()` returns a flat list of literals and group numbers, and
  `expand_template()` is gone
- **Python 3.13+**: `PatternError` is the exception's name, and the inline `t` flag is no longer
  accepted
- **All Python 3**: Undocumented; the deprecation names no removal release

## Related Modules

- **[re](re.md)** - the public API; the cost of compiling, caching and matching a pattern
- **[sre_compile](sre_compile.md)** - turns the tree `parse()` returns into a compiled pattern
- **[sre_constants](sre_constants.md)** - the opcodes a parse tree is made of
