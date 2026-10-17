# String Operations Complexity

The `str` type is an immutable sequence of Unicode characters. CPython stores every string at one
fixed width per character, 1, 2 or 4 bytes chosen by its widest character, so indexing is direct.
Because a string cannot change, copying an exact `str` returns the string itself.

`n` is the string's length, `m` the length of a string argument (`sub`, `prefix`, `sep`, `old`),
`r` the length of the result, `k` a repeat count, `w` a requested width and `c` the length of a
`chars` argument. `i:j` are slice bounds, counted after negative values are normalized. With `start`
and `end` arguments, `n` is the length of the region searched, which is read in place rather than
copied. A multi-character argument stored narrower than `s`, such as an ASCII substring in text
holding a CJK character, is first copied at `s`'s width: O(m) extra space for the search methods,
`count()`, `replace()`, `split()`, `rsplit()`, `partition()` and `rpartition()`.

## Complexity Reference

### str

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | The length is stored in the string, not counted |
| `s[k]` | O(1) | O(1) | Direct indexing; the result is a one-character string |
| `s[i:j]` (slicing) | O(j-i) | O(j-i) | With a step, O(r); `s[:]` of an exact `str` returns `s` itself |
| `s[:]`, `str(s)`, `copy.copy(s)` | O(1) | O(1) | Return `s` itself when it is an exact `str`; a subclass instance is copied in O(n) |
| `s + t` (concatenation) | O(n+len(t)) | O(n+len(t)) | Returns the other operand itself when one is empty; building a string by `+=` in a loop is O(r²) at worst |
| `s * k` (repetition) | O(nk) | O(nk) | k ≤ 0 gives an empty string; `s * 1` returns `s` itself |
| `s == t` | O(n) | O(1) | O(1) when the lengths or the character widths differ, or both are the same object |
| `s < t`, `<=`, `>`, `>=` | O(min(n, len(t))) | O(1) | Stops at the first unequal character |
| `hash(s)` | O(n) first call; O(1) after | O(1) | The result is kept in the string; an equal string built separately pays its own first hash |
| `for c in s` | O(n) | O(1) | One single-character string per step |
| `sub in s` (substring) | O(n) | O(1), O(m) to widen | Forward search with a linear worst case; a substring longer than the string returns at once |
| **Search** ||||
| `find(sub, start, end)` | O(n) | O(1), O(m) to widen | Forward search; n = characters searched |
| `rfind(sub, start, end)` | O(n·m) worst | O(1), O(m) to widen | Reverse search; O(n) on typical input |
| `index(sub, start, end)` | O(n) | O(1), O(m) to widen | Like `find()` but raises `ValueError` if not found |
| `rindex(sub, start, end)` | O(n·m) worst | O(1), O(m) to widen | Like `rfind()` but raises `ValueError` if not found |
| `count(sub, start, end)` | O(n) | O(1), O(m) to widen | Forward search |
| `startswith(prefix)` | O(m) | O(1) | Compares only the prefix |
| `endswith(suffix)` | O(m) | O(1) | Compares only the suffix |
| **Replace/Translate** ||||
| `replace(old, new)` | O(n + r) | O(r), O(m) to widen | Forward search for `old`; returns `s` itself when `old` does not occur |
| `translate(table)` | O(n + r) | O(n + r) | Counting each table lookup as O(1); a mapping to longer strings makes r exceed n |
| `str.maketrans(x, y, z)` | O(e) | O(e) | e = characters or dict entries in the arguments; a static method |
| `expandtabs(tabsize)` | O(n + r) | O(r) | Each tab grows the result by up to `tabsize`; with no tab, returns `s` itself |
| `removeprefix(prefix)` | O(n) | O(n) | Copies the rest when `prefix` matches; otherwise O(m) and returns `s` itself |
| `removesuffix(suffix)` | O(n) | O(n) | Copies the rest when `suffix` matches; otherwise O(m) and returns `s` itself |
| **Split/Join** ||||
| `split(sep)` | O(n) | O(n) | Forward search for `sep` |
| `rsplit(sep)` | O(n·m) worst | O(n) | Searches backwards as `rfind()` does; O(n) with no `sep` or a one-character one |
| `splitlines()` | O(n) | O(n) | Splits on line boundaries |
| `partition(sep)` | O(n) | O(n) | Forward search for the first `sep` |
| `rpartition(sep)` | O(n·m) worst | O(n) | Searches backwards as `rfind()` does |
| `sep.join(iterable)` | O(r + p) | O(r + p) | p = pieces; an iterable that is not a list or tuple is collected into a list first; a single exact `str` piece is returned itself |
| **Case Conversion** ||||
| `upper()` | O(n) | O(n) | |
| `lower()` | O(n) | O(n) | |
| `capitalize()` | O(n) | O(n) | Titlecase first, lowercase rest |
| `title()` | O(n) | O(n) | Titlecase words |
| `swapcase()` | O(n) | O(n) | |
| `casefold()` | O(n) | O(n) | For caseless matching |
| **Stripping** ||||
| `strip(chars)` | O(n + (d+1)·c) | O(n) | d = characters stripped, each looked up in `chars`; returns `s` itself when nothing is stripped |
| `lstrip(chars)` | O(n + (d+1)·c) | O(n) | As `strip()`, from the left |
| `rstrip(chars)` | O(n + (d+1)·c) | O(n) | As `strip()`, from the right |
| **Padding/Alignment** ||||
| `center(width)` | O(w) | O(w) | Returns `s` itself when w ≤ n |
| `ljust(width)` | O(w) | O(w) | Returns `s` itself when w ≤ n |
| `rjust(width)` | O(w) | O(w) | Returns `s` itself when w ≤ n |
| `zfill(width)` | O(w) | O(w) | Returns `s` itself when w ≤ n |
| **Predicates** ||||
| `isalnum()` | O(n) | O(1) | |
| `isalpha()` | O(n) | O(1) | |
| `isascii()` | O(1) | O(1) | Reads a flag the `str` keeps |
| `isdecimal()` | O(n) | O(1) | |
| `isdigit()` | O(n) | O(1) | |
| `isidentifier()` | O(n) | O(1) | |
| `islower()` | O(n) | O(1) | |
| `isnumeric()` | O(n) | O(1) | |
| `isprintable()` | O(n) | O(1) | |
| `isspace()` | O(n) | O(1) | |
| `istitle()` | O(n) | O(1) | |
| `isupper()` | O(n) | O(1) | |
| **Formatting** ||||
| `format(*args, **kwargs)` | O(n) + each field's `format()` | O(n) + each field's `format()` | n = template length; see [format()](format.md) |
| `format_map(mapping)` | O(n) + each field's `format()` | O(n) + each field's `format()` | Like `format()` with a mapping |
| `s % values` | O(n) + each conversion | O(n) + each conversion | `%s` calls `str()`; see [format()](format.md) |
| **Encoding** ||||
| `encode(encoding)` | O(n) | O(n) | Converts to bytes; assumes a codec doing constant work per character |

## Copying Returns the Same String

A copy of an exact string could never differ from the original, so `s[:]`, `str(s)` and
`copy.copy(s)` hand back `s` itself in O(1). Several methods do the same when they have nothing to
change: padding to a width no larger than the string, stripping when nothing matches, `replace()`
when `old` does not occur, and `join()` of a single string. A subclass instance is copied in O(n).

```python
import copy

s = "x" * 1_000_000
assert s[:] is s  # O(1)
assert str(s) is s  # O(1)
assert copy.copy(s) is s  # O(1)

assert s.center(10) is s  # w <= n
assert s.strip() is s  # nothing to strip
assert s.replace("y", "z") is s  # "y" does not occur
assert "".join([s]) is s  # a single piece


class Text(str):
    pass


t = Text("abc")
assert str(t) is not t and type(str(t)) is str  # O(n): a subclass is copied
```

## Character Width

Each string is stored at the width its widest character needs: 1 byte per character up to U+00FF,
2 bytes up to U+FFFF, and 4 bytes beyond. A single wide character makes the whole string wide, which
is why a narrower substring has to be widened before it is searched for.

```python
import sys


def bytes_per_char(ch):
    return (sys.getsizeof(ch * 2_000) - sys.getsizeof(ch * 1_000)) // 1_000


assert bytes_per_char("a") == 1
assert bytes_per_char("é") == 1
assert bytes_per_char("世") == 2
assert bytes_per_char("😀") == 4

# One CJK character makes all 1,000 ASCII characters take 2 bytes each
assert sys.getsizeof("世" + "a" * 1_000) - sys.getsizeof("世") == 2_000
```

## Building Strings

Each `+` of two non-empty strings builds a new string, so a loop of `+=` can copy everything built
so far at every step, O(r²) in the total length. CPython can sometimes grow the string in place
instead, but only while nothing else refers to it: keeping any other reference to the partial result
makes every step copy. `join()` sizes the result once and copies each piece once.

```python
pieces = [str(i) for i in range(10_000)]

joined = "".join(pieces)  # O(r + p)

built = ""
for piece in pieces:
    built += piece  # O(r²) at worst

assert built == joined
```

## Substring Search

The forward searches (`in`, `find()`, `index()`, `count()`, and the search in `split()`,
`partition()` and `replace()`) have a linear worst case. The reverse searches (`rfind()`, `rindex()`,
`rsplit()`, `rpartition()`) are O(n) on typical input but O(n·m) at worst. With `start` and `end`,
only that region is read, and unlike slicing first nothing is copied.

```python
s = "a" * 1_000_000 + "b"

assert s.find("b") == 1_000_000  # O(n)
assert s.find("b", 0, 1_000) == -1  # O(1,000): only the region is read
assert "a" * 999 + "b" in s  # O(n), however long the pattern
assert s.rfind("ba") == -1  # O(n) here, O(n·m) at worst
```

## Performance Best Practices

✅ **Do**:

- Build a string from many pieces with `"".join(pieces)`: O(r + p) once
- Pass `start` and `end` to `find()` or `count()` instead of slicing first: the region is read in
  place, while a slice copies O(j-i) characters
- Prefer a forward search to a reverse one for long patterns: O(n) against O(n·m) at worst

❌ **Avoid**:

- `+=` in a loop over many pieces, above all while another reference to the partial string exists
- Long `chars` arguments to `strip()`: each stripped character is looked up in `chars`

## Related Types

- **[Bytes](bytes.md)** - Immutable byte sequence
- **[Bytearray](bytearray.md)** - Mutable byte sequence
- **[str()](str_func.md)** - Converting objects to strings
- **[format()](format.md)** - f-strings, `str.format()` and `%` formatting
- **[Regex (re)](../stdlib/re.md)** - Pattern matching

## Further Reading

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  Deep dive into CPython's str implementation
