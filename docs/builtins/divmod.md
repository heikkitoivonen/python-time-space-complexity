# divmod() Function Complexity

The `divmod(a, b)` function returns the floor quotient and the remainder as one tuple,
`(a // b, a % b)`. On large ints it divides once where `//` and `%` each divide.

For ints, `n` is the size of the dividend `a` and `m` the size of the divisor `b`, both in bits.
When `m > n` the quotient is 0 or -1, and the call is O(n + m).
Ints that fit in a machine word and all floats are priced at O(1).

## Complexity Reference

### divmod()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `divmod(a, b)` on machine-size ints | O(1) | O(1) | |
| `divmod(a, b)` on floats or mixed int and float | O(1) | O(1) | The int is converted to a float |
| `divmod(a, b)` on large ints | O(m·(n − m + 1)) | O(n + m) | O(n) for a small divisor; O(n²) when the divisor is about half the dividend's size |
| `divmod(a, b)` on large ints, Python 3.12+ | O((n + m)^log₂3) | O(n + m) | Used when both the divisor and the quotient are thousands of bits long; smaller cases keep the bound above |
| `divmod(a, b)` on other types | `__divmod__` | `__divmod__` | Uses the operands' `__divmod__` or `__rdivmod__` |

## Basic Usage

### Integer Division

```python
# O(1) - quotient and remainder in one call
assert divmod(17, 5) == (3, 2)   # 17 == 5 * 3 + 2
assert divmod(20, 3) == (6, 2)   # 20 == 3 * 6 + 2
assert divmod(10, 2) == (5, 0)   # 10 == 2 * 5 + 0

assert divmod(17, 5) == (17 // 5, 17 % 5)
```

### Float Division

```python
# O(1) - floating point division
assert divmod(17.5, 5) == (3.0, 2.5)
assert divmod(10.0, 3.0) == (3.0, 1.0)

# Mixed int and float give floats
assert divmod(17, 5.0) == (3.0, 2.0)
```

### Negative Numbers

The quotient is rounded toward negative infinity, so the remainder takes the sign of the
divisor.

```python
# O(1)
assert divmod(-17, 5) == (-4, 3)     # -17 == 5 * -4 + 3
assert divmod(17, -5) == (-4, -3)    # 17 == -5 * -4 + -3
assert divmod(-17, -5) == (3, -2)    # -17 == -5 * 3 + -2
assert divmod(-10, 3) == (-4, 2)     # not (-3, -1): that is truncation
```

## Large Integers

The cost of dividing large ints depends on both operands. A small divisor is a single linear
pass over the dividend; a divisor about half the dividend's size is the worst case for
schoolbook division. From Python 3.12, a large divisor with a large quotient switches to a
subquadratic algorithm.

```python
a = 10**1000
q, r = divmod(a, 7)            # O(n) - small divisor
assert a == 7 * q + r and 0 <= r < 7

b = 10**500
q, r = divmod(a, b)            # O(n²) before 3.12 - divisor half the dividend's size
assert (q, r) == (10**500, 0)
```

## divmod() vs // and %

On large ints, `divmod()` computes both results from one division, while `a // b` and `a % b`
each divide, so `divmod()` is the cheaper way to get both. On machine-size ints neither spelling
is consistently faster.

```python
a = 3**20000
b = 7**5000

q, r = divmod(a, b)            # one division
assert (q, r) == (a // b, a % b)  # two divisions
```

## Common Patterns

### Converting to Another Base

For `num >= 0` and a fixed base of 2 or more, each step divides by the base, so a number of
`d` digits in the target base takes `d` calls. Each call is O(1) for machine-size ints and O(n)
for a large one, which makes the whole loop O(n·d) on large ints.

```python
def to_base(num, base):
    digits = []
    while num:
        num, remainder = divmod(num, base)   # O(1) on machine-size ints
        digits.append(remainder)
    return digits[::-1]

assert to_base(42, 2) == [1, 0, 1, 0, 1, 0]
assert to_base(255, 16) == [15, 15]           # 0xFF
```

### Splitting Durations

```python
# O(1) per call on machine-size ints
def format_seconds(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

assert divmod(125, 60) == (2, 5)
assert format_seconds(3665) == "01:01:05"
```

### Counting Pages

```python
# O(1)
items = 125
page_size = 10
full_pages, leftover = divmod(items, page_size)
assert (full_pages, leftover) == (12, 5)

total_pages = full_pages + (leftover > 0)
assert total_pages == 13 == -(-items // page_size)
```

## Edge Cases

```python
# O(1)
assert divmod(0, 5) == (0, 0)
assert divmod(5, 1) == (5, 0)
assert divmod(5, -1) == (-5, 0)

try:
    divmod(5, 0)
except ZeroDivisionError as exc:
    assert "by zero" in str(exc)
else:
    raise AssertionError("divmod(5, 0) did not raise")
```

## Performance Best Practices

✅ **Do**:

- Use `divmod()` when you need both the quotient and the remainder of large ints - one division instead of two

❌ **Avoid**:

- Repeated subtraction in a loop to find a quotient - O(q) steps where `divmod()` divides once

## Related Functions

- **[int](int.md)** - The `//` and `%` operators on ints
- **[float](float.md)** - Floor division and remainder on floats
- **[pow()](pow.md)** - Modular exponentiation
- **[math](../stdlib/math.md)** - `math.fmod()`, a remainder with the sign of the dividend

## Version Notes

- **Python 3.12+**: Large ints with a large divisor and a large quotient are divided in O((n + m)^log₂3) rather than O(m·(n − m + 1))
- **All Python 3**: For ints, `divmod(a, b)` equals `(a // b, a % b)`
