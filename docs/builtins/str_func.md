# str() Function Complexity

`str(obj)` returns the informal text form of an object by calling its `__str__()`, which falls
back to `__repr__()` when the class defines no `__str__()`. `str(b, encoding, errors)` instead
decodes a bytes-like object. What the resulting string costs to use is on the [str](str.md) page.

`n` is the length of the argument, in characters for a `str` and in bytes for a bytes-like
object. `L` is the length of the result. For a container, `h` is how deeply it nests: 1 for a
list of numbers, 2 for a list of lists. `d` is the decimal digits of an int.

## Complexity Reference

### str()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `str()` | O(1) | O(1) | The empty string |
| `str(s)` on an exact `str` | O(1) | O(1) | Returns `s` itself |
| `str(s)` on a `str` subclass instance without its own `__str__()` | O(n) | O(n) | Copied into a new exact `str` |
| `str(x)` for a `bool`, `None`, `float` or `complex` | O(1) | O(1) | A `float` needs at most 24 characters |
| `str(i)` for an `int` | O(d²); 3.12+: subquadratic above 30,000 bits | O(d) | Raises `ValueError` beyond `sys.get_int_max_str_digits()`, 4,300 digits by default, which is below the subquadratic range; see [int](int.md) |
| `str(c)` for a list, tuple, dict or set | O(L × h) plus each element's `repr()` | O(L) | Calls `repr()`, not `str()`, on each element; every level of nesting copies the text of the levels inside it once more |
| `str(b)` for `bytes` or `bytearray`, no encoding | O(n) | O(n) | The `repr()`, such as `b'abc'`; nothing is decoded |
| `str(b, encoding, errors)` | O(n) | O(n) | Decodes, assuming a codec that does a constant amount of work per byte; a `str` argument raises `TypeError` |
| `str(obj)` with a custom `__str__()` | Cost of `__str__()` | Cost of `__str__()` | `__str__()` must return a `str`, or `str()` raises `TypeError` |

## Strings and Bytes

### Returning a String Unchanged

A `str` is immutable, so `str(s)` on an exact `str` returns the same object at no cost, however
long it is. An instance of a `str` subclass is copied into a plain `str`, which costs O(n).

```python
text = "x" * 1_000_000
assert str(text) is text  # O(1) - the same object
assert str() == ""  # O(1)

class Label(str):
    pass

label = Label("ok")
plain = str(label)  # O(n) - a new exact str
assert plain == "ok" and type(plain) is str and plain is not label
```

### Decoding Bytes

Without an encoding, `str()` on bytes returns their `repr()`, quotes and `b` prefix included.
Passing an encoding decodes them instead, in O(n) for a codec such as UTF-8 that does a constant
amount of work per byte; `bytes.decode()` does the same work.

```python
data = "café".encode("utf-8")  # O(n)

assert str(data) == "b'caf\\xc3\\xa9'"  # O(n) - the repr, not a decode
assert str(data, "utf-8") == "café"  # O(n)
assert str(data, "utf-8") == data.decode("utf-8")
assert str(b"\xff", "utf-8", "replace") == "�"

try:
    str("café", "utf-8")
except TypeError as error:
    assert "decoding str is not supported" in str(error)
else:
    raise AssertionError("expected TypeError")
```

## Numbers and Containers

### Numbers

`bool`, `None`, `float` and `complex` values convert in O(1): a `float` uses the shortest text
that reads back as the same value, at most 24 characters. An int's decimal text is the expensive
case, quadratic in its digits up to the default digit limit, and CPython refuses it beyond that
limit. `hex()` and `bin()`
are linear and have no limit.

```python
import sys

assert str(True) == "True" and str(None) == "None"  # O(1)
assert str(0.1) == "0.1"  # O(1)
assert str(-2.2250738585072014e-308) == "-2.2250738585072014e-308"  # 24 characters

big = 7 ** 6_000  # about 5,000 decimal digits
try:
    str(big)  # O(d²) - beyond the default limit of 4,300 digits
except ValueError as error:
    assert "limit" in str(error)
else:
    raise AssertionError("expected ValueError")

assert len(hex(big)) == (big.bit_length() + 3) // 4 + 2  # O(d) - no limit

limit = sys.get_int_max_str_digits()
sys.set_int_max_str_digits(0)  # 0 removes the limit
try:
    assert len(str(big)) == 5_071
finally:
    sys.set_int_max_str_digits(limit)
```

### Containers

`str()` on a list, tuple, dict or set calls `repr()` on each element, so strings inside appear with
their quotes. A flat container costs O(L) plus its elements' `repr()`. Each nested container
builds its own text, which its parent then copies, so text `h` levels deep is copied `h` times. A
container that holds itself appears as `[...]` or `{...}`.

```python
class Point:
    def __str__(self):
        return "point"

    def __repr__(self):
        return "Point()"

assert str(["a", 1]) == "['a', 1]"  # O(L) - repr() of each element
assert str([Point()]) == "[Point()]"  # __repr__, not __str__
assert str({"k": (1, 2)}) == "{'k': (1, 2)}"

loop = [1, 2]
loop.append(loop)
assert str(loop) == "[1, 2, [...]]"
```

## Custom Objects

### Defining \_\_str\_\_()

`str()` costs whatever `__str__()` costs, and calls it once. A class without `__str__()` gets
`__repr__()`'s text. Returning anything other than a `str` raises `TypeError`.

```python
class Temperature:
    def __init__(self, celsius):
        self.celsius = celsius

    def __str__(self):
        return f"{self.celsius} °C"

    def __repr__(self):
        return f"Temperature({self.celsius})"

class Plain:
    def __repr__(self):
        return "Plain()"

class Broken:
    def __str__(self):
        return 42

assert str(Temperature(21)) == "21 °C"
assert str(Plain()) == "Plain()"  # Falls back to __repr__

try:
    str(Broken())
except TypeError:
    pass
else:
    raise AssertionError("expected TypeError")
```

## Common Patterns

### Joining Converted Values

`"".join(map(str, items))` converts each item once and copies the pieces into the result once,
O(k + L) in total for `k` items that each convert in O(1).

```python
items = [1, 2.5, None, "x"]
assert ", ".join(map(str, items)) == "1, 2.5, None, x"  # O(k + L)
```

### Deferring Conversion in Logging

An f-string passed to a logging call converts its values before the call, even when the message's
level is disabled. Passing the values as arguments defers `str()` until a handler emits the
record, so a disabled message costs no conversion.

```python
import logging

class Expensive:
    calls = 0

    def __str__(self):
        Expensive.calls += 1
        return "expensive"

logger = logging.getLogger("str-example")
logger.setLevel(logging.WARNING)
value = Expensive()

logger.info(f"value: {value}")  # Converts now, then drops the message
assert Expensive.calls == 1

logger.info("value: %s", value)  # Dropped before any conversion
assert Expensive.calls == 1
```

## Performance Best Practices

✅ **Do**:

- Rely on `str(s)` of an exact `str` being free; it returns the same object
- Pass values as arguments to logging calls rather than formatting them first
- Use `hex()` or `bin()` for very large ints; decimal text is quadratic up to the default digit
  limit and refused beyond it

❌ **Avoid**:

- `str()` on a large or deeply nested container just to log its size; its text costs O(L × h)
- Raising `sys.set_int_max_str_digits()` to convert untrusted ints to decimal
- Expecting `str(b)` on bytes to decode them; pass an encoding

## Related Functions

- **[str](str.md)** - What the string you built costs to use
- **[repr()](repr.md)** - The representation containers use for their elements
- **[format()](format.md)** - Format with a spec
- **[ascii()](ascii.md)** - ASCII-safe representation
- **[bytes()](bytes_func.md)** - Encode to bytes
- **[int](int.md)** - Decimal conversion and its digit limit
