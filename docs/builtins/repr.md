# repr() Function Complexity

`repr(x)` calls `type(x).__repr__(x)` once and returns the string it produces. The built-in
scalars render themselves directly. The built-in containers call `repr()` on every element and
join the results, so their cost is the elements' own reprs plus the length of what they build.
Nothing is cached: each call renders the object again.

`L` is the length of the returned string. For a `str`, `bytes` or `bytearray`, `n` is its length;
for a container, `n` is its elements, and the bound adds each element's own repr, recursively.
`d` is the decimal digits of an `int`, `h` is how many levels deep containers nest inside one
another, and `r` is the cost of a user-defined `__repr__`.

## Complexity Reference

### Built-in scalars

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `repr(x)` for `None`, a `bool`, a `float` or a `complex` | O(1) | O(1) | A float renders as the shortest string that reads back as the same value |
| `repr(x)` for an `int` | O(d²) | O(d) | Raises `ValueError` beyond `sys.get_int_max_str_digits()`, 4,300 digits by default; see [int](int.md) |
| `repr(s)` for a `str` | O(n) | O(n) | Adds quotes and escapes; one character can become up to 10 (`'\U000e0001'`) |
| `repr(b)` for `bytes` or a `bytearray` | O(n) | O(n) | One byte can become up to 4 characters (`\xff`) |

### Containers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `repr(x)` for a `list` or `tuple` | O(L) plus the elements' reprs | O(L) | Calls `repr()` once per element |
| `repr(x)` for a `dict`, `set` or `frozenset` | O(L) plus the keys' and values' reprs | O(L) | Walks the hash table: one that had most of its items removed costs its former size (see [dict](dict.md)) |
| Containers nested `h` levels deep | O(L·h) at most | O(L) | Each container copies the text of what it holds, so text `h` levels down is copied again at each level |
| A container that contains itself | O(h) for the repeat | O(1) | Shows `[...]`, `(...)` or `{...}` instead of recursing |

### User-defined objects

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `repr(obj)` with the default `object.__repr__` | O(1) | O(1) | `<module.Name object at 0x...>` |
| `repr(obj)` with a `__repr__` | O(r) | O(r) | Called once; a result that is not a `str` raises `TypeError` |
| `str(x)` for a type with no `__str__`, `f"{x!r}"`, `"%r" % x` | As `repr(x)` | As `repr(x)` | The built-in containers have no `__str__`, so `str()` of one renders its elements with `repr()` |

## Strings

A string's repr is a pass over its characters: it picks the quote, then escapes backslashes,
the chosen quote and every character that is not printable. The result reads back as the same
string, which is what makes it useful for debugging.

```python
assert repr("hello") == "'hello'"  # O(n)
assert repr("it's") == '"it\'s"'  # Double quotes avoid an escape
assert repr("tab\there") == "'tab\\there'"
assert repr("café") == "'café'"  # Printable non-ASCII is kept; ascii() escapes it
assert repr("\U000e0001") == "'\\U000e0001'"  # One character, ten in the result

s = "line 1\nline 2 'quoted' \"too\""
assert eval(repr(s)) == s  # Reads back as the same string
```

## Integers

Converting an int to decimal is quadratic in its digits, so `repr()` refuses an int longer than
`sys.get_int_max_str_digits()` rather than spending that time. Hex is linear and has no limit.

```python
import sys

assert repr(2**64) == "18446744073709551616"  # O(d²), d = 20

big = 10**5000  # 5,001 digits
try:
    repr(big)
except ValueError as error:
    assert "Exceeds the limit" in str(error)
else:
    raise AssertionError("repr() rendered more digits than the limit allows")

assert sys.get_int_max_str_digits() == 4300
assert int(hex(big), 16) == big  # O(d) - power-of-two bases are not limited
```

## Containers

### Each Element Renders Itself

A container calls `repr()` on each element once, so a slow `__repr__` costs once per element on
every call. `str()` of a built-in container gives the same text: containers have no `__str__`,
and the elements always appear in their repr form.

```python
class Item:
    calls = 0

    def __init__(self, value):
        self.value = value

    def __repr__(self):
        Item.calls += 1
        return f"Item({self.value})"

items = [Item(i) for i in range(3)]
assert repr(items) == "[Item(0), Item(1), Item(2)]"  # O(L) plus 3 __repr__ calls
assert Item.calls == 3

text = str(items)  # Calls __repr__ three more times
assert text == "[Item(0), Item(1), Item(2)]"
assert Item.calls == 6
assert str(["a", 1]) == "['a', 1]"  # The string element is quoted
assert repr({"a": [1, 2], "b": (3,)}) == "{'a': [1, 2], 'b': (3,)}"
```

### Nesting and Self-Reference

A container renders each element to a string and copies it into its own result, so text nested
`h` levels down is copied again at each level. A wide, shallow structure costs close to O(L); a
chain of `h` nested lists, where `L` grows with `h`, costs O(h²). A container that holds itself
is shown as `[...]` or `{...}` instead of being rendered again.

```python
lst = [1, 2]
lst.append(lst)
assert repr(lst) == "[1, 2, [...]]"  # The repeat is not rendered again

d = {"a": 1}
d["self"] = d
assert repr(d) == "{'a': 1, 'self': {...}}"

chain = []
for _ in range(50):
    chain = [chain]
assert repr(chain) == "[" * 51 + "]" * 51  # O(h²) - L grows with h
```

## Common Patterns

### Truncating Large Output

Slicing `repr(x)` afterwards still renders all of `x` first. `reprlib.repr()` renders only the
first few elements of a list or tuple and the two ends of a string, so its cost does not grow with
them; it sorts a dict or set first, which costs O(n log n).

```python
import reprlib

data = list(range(100_000))

whole = repr(data)[:20]  # O(L) - every element is rendered, then cut
assert whole == "[0, 1, 2, 3, 4, 5, 6"

short = reprlib.repr(data)  # Reads 6 elements
assert short == "[0, 1, 2, 3, 4, 5, ...]"
```

### Deferring repr in Logging

An f-string renders its arguments before the call, whether or not the message is logged.
Passing `%r` and the object lets `logging` call `repr()` only for a record it emits.

```python
import logging

class Expensive:
    calls = 0

    def __repr__(self):
        Expensive.calls += 1
        return "Expensive()"

log = logging.getLogger("repr-example")
log.setLevel(logging.WARNING)
obj = Expensive()

log.debug("state: %r", obj)  # Not emitted, so repr() is never called
assert Expensive.calls == 0

log.debug(f"state: {obj!r}")  # Rendered before the call, then dropped
assert Expensive.calls == 1
```

## Performance Best Practices

✅ **Do**:

- Pass `%r` and the object to `logging` so `repr()` runs only for records that are emitted
- Use `reprlib.repr()` to show a large list, tuple or string: it renders only a few items
- Keep `__repr__` cheap: a container calls it once per element on every render

❌ **Avoid**:

- `repr(x)[:k]` to shorten output: the whole repr is built first
- `repr()` of a very large int: it is quadratic in the digits and raises past the limit; use
  `hex()` or the int's bit length when the digits are not needed
- Deeply nested structures: every level copies the text below it again

## Related Functions

- **[ascii()](ascii.md)** - `repr()` with non-ASCII characters escaped
- **[str()](str_func.md)** - The readable form; the same as `repr()` for containers
- **[format()](format.md)** - Format with a specification
- **[int](int.md)** - Decimal conversion and its digit limit
- **[reprlib](../stdlib/reprlib.md)** - Size-limited representations
- **[print()](print.md)** - Calls `str()` on its arguments
