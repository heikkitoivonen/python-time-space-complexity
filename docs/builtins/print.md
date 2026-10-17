# print() Function Complexity

The `print()` function converts each argument with `str()` and writes the results to a file,
`sys.stdout` by default, with a separator between them and `end` after the last. It never joins the
output into one string: each piece goes to the file's `write()` method as soon as it is converted.

`n` is the characters written and `k` is the arguments. `m` is the length of the longest argument
after conversion. Converting an argument costs what its `__str__` does: an exact `str` is passed on
as it is, and a container's text is built from its items. The bounds exclude passing the k arguments
into the call. A call of `file.write(s)` is priced at O(len(s)), as it is for a text file or
`io.StringIO`; when the text reaches the operating system depends on the file's buffering, not on
`print()`.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `print(*objects)` | O(n + k) | O(m) | One `str()` and one `write()` per argument, one `write()` per separator and one for `end`: 2k calls for k ≥ 1 arguments. Each converted argument is released before the next is converted |
| `print(s)` with an exact `str` | O(len(s)) | O(1) | `s` itself is passed to `write()`, without a copy; a `str` subclass is converted to a new `str` |
| `print()` | O(1) | O(1) | Writes only `end` |
| `print(*objects, sep=s, end=e)` | O(n + k) | O(m) | `sep` and `end` must be `str` or `None`; anything else raises `TypeError` before anything is written |
| `print(*objects, file=f)` | O(n + k) | O(m) | `f` needs only a `write()` method; `file=None` means `sys.stdout` |
| `print(*objects, flush=True)` | O(n + k) | O(m) | Plus one call of `f.flush()` after `end` is written |
| `print(*objects)` while `sys.stdout` is `None` | O(1) | O(1) | Returns without converting or writing anything |

## Writing Output

### One write() per Piece

`print()` hands each converted argument, each separator and the final `end` to `write()` in turn,
so a file object sees 2k calls for k ≥ 1 arguments.

```python
class Recorder:
    def __init__(self):
        self.calls = []

    def write(self, text):
        self.calls.append(text)
        return len(text)

out = Recorder()
print("x =", 42, [1, 2], file=out)  # O(n + k) - 3 arguments, 6 writes

assert out.calls == ["x =", " ", "42", " ", "[1, 2]", "\n"]
```

### Separators and End

`sep` goes between arguments and `end` after the last; both must be strings or `None`.

```python
import io

buffer = io.StringIO()
print("a", "b", "c", sep=", ", file=buffer)
print("no newline", end="", file=buffer)
print("x", "y", sep="-", end="!\n", file=buffer)
assert buffer.getvalue() == "a, b, c\nno newlinex-y!\n"

try:
    print("a", "b", sep=0, file=buffer)
except TypeError as error:
    assert "sep must be None or a string" in str(error)
else:
    raise AssertionError("expected TypeError")
assert buffer.getvalue() == "a, b, c\nno newlinex-y!\n"  # Nothing was written
```

### Strings Are Not Copied

An exact `str` argument goes to `write()` unchanged, and other arguments are converted one at a time, so
the extra memory `print()` needs is the longest converted argument, not the whole output.

```python
class Recorder:
    def __init__(self):
        self.calls = []

    def write(self, text):
        self.calls.append(text)
        return len(text)

text = "x" * 100_000
out = Recorder()
print(text, file=out)  # O(1) extra space

assert out.calls[0] is text
```

## Buffering and Flushing

`print()` only calls `write()`. A regular file opened for writing is block-buffered, so short output
stays in Python's buffer until the buffer fills, the file is flushed or closed. `flush=True` adds
one `flush()` call, which pushes the buffered text to the operating system.

```python
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, "out.txt")
    with open(path, "w", newline="") as f:
        print("first", file=f)
        assert os.path.getsize(path) == 0  # Still buffered

        print("second", file=f, flush=True)  # One extra flush() call
        assert os.path.getsize(path) == len("first\nsecond\n")
```

## Printing Many Lines

Printing line by line makes two `write()` calls per line and holds one line at a time. Joining
first makes two calls in all, but builds the whole output as one string before writing it.

```python
class Recorder:
    def __init__(self):
        self.calls = []

    def write(self, text):
        self.calls.append(text)
        return len(text)

lines = [f"Item {i}" for i in range(1_000)]

per_line = Recorder()
for line in lines:
    print(line, file=per_line)  # 2 writes per line, O(1) extra space

joined = Recorder()
print("\n".join(lines), file=joined)  # 2 writes, O(n) extra space for the joined string

assert len(per_line.calls) == 2_000
assert len(joined.calls) == 2
assert "".join(per_line.calls) == "".join(joined.calls)
```

## Edge Cases

### No Standard Output

When `sys.stdout` is `None`, as under `pythonw` on Windows, `print()` returns at once: the arguments
are not even converted.

```python
import sys

class Loud:
    def __str__(self):
        raise AssertionError("converted")

saved = sys.stdout
sys.stdout = None
try:
    print(Loud())  # O(1) - nothing is converted or written
finally:
    sys.stdout = saved
```

### Containers and Large Integers

A container's text is built from its items, and a self-referencing list prints `[...]` for the
cycle instead of recursing. Under the default limit of 4,300 decimal digits, an `int` with more
digits is refused.

```python
import io

buffer = io.StringIO()
cycle = []
cycle.append(cycle)
print(cycle, file=buffer)
assert buffer.getvalue() == "[[...]]\n"

try:
    print(10 ** 5_000, file=buffer)
except ValueError as error:
    assert "integer string conversion" in str(error)
else:
    raise AssertionError("expected ValueError")
```

## Performance Best Practices

✅ **Do**:

- Print large output line by line or in chunks; `print()` never holds more than one converted
  argument
- Pass `flush=True` when output must appear at once, such as progress on a file or pipe
- Pass `file=` to write to any object with a `write()` method, such as `io.StringIO`

❌ **Avoid**:

- Joining everything into one string just to print it; it saves `write()` calls but holds the
  whole output in memory
- `flush=True` on every line of bulk output to a file; it hands each line to the operating system
  separately instead of a buffer at a time
- Printing an `int` over the digit limit, 4,300 digits by default; it raises `ValueError` unless
  the limit is raised

## Related Functions

- **[str()](str.md)** - The conversion `print()` applies to each argument
- **[repr()](repr.md)** - What containers use for their items' text
- **[int()](int.md)** - The digit limit on decimal conversion
- **[open()](open.md)** - Files to pass as `file=`, and their buffering
- **[input()](input.md)** - Read a line from standard input
