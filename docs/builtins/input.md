# input() Function Complexity

`input()` writes an optional prompt, reads one line from `sys.stdin`, and returns it without its
trailing newline. When `sys.stdin` and `sys.stdout` are both the process's terminal it reads
through the interpreter's line reader, with the `readline` module's line editing if that module
has been imported; otherwise - a pipe, a file, or a replaced `sys.stdin` such as `io.StringIO` -
it calls `sys.stdin.readline()`.

`k` is the characters of the line read, `m` the characters of `str(prompt)`, `n` the lines read
by a loop and `t` their total characters. `h` is the entries in the `readline` module's history.
Building the prompt, such as formatting an f-string, is the caller's work and is not counted.

## Complexity Reference

### input

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `input()` | O(k) | O(k) | Returns the line without its trailing newline; other whitespace is kept |
| `input(prompt)` | O(m + k) | O(m + k) | Writes `str(prompt)` with no newline before reading |
| `input()` at end of input | O(1) | O(1) | Raises `EOFError` |
| `input()` on a terminal with `readline` imported | O(k + h) libedit, O(k) GNU | O(k) | Also appends the line to the in-memory history, which is kept across calls, unless it repeats the newest entry; see [readline](../stdlib/readline.md) |

## Reading a Line

The trailing newline is removed; leading and trailing spaces are not. Off a terminal, a last
line with no newline is returned whole.

```python
import io
import sys

sys.stdin = io.StringIO("  Alice  \nBob")

name = input()  # O(k)
assert name == "  Alice  "
assert name.strip() == "Alice"  # O(k)
assert input() == "Bob"
```

At the end of input `input()` raises `EOFError` rather than returning an empty string, which
it returns for an empty line.

```python
import io
import sys

sys.stdin = io.StringIO("\n")

assert input() == ""  # an empty line
try:
    input()  # O(1): nothing left
except EOFError as error:
    assert str(error) == "EOF when reading a line"
else:
    raise AssertionError("input() at end of input should raise EOFError")
```

## The Prompt

Anything that is not a `str` is converted with `str()` first, and no newline is added. Off a
terminal the prompt is written to `sys.stdout`, which is flushed before the line is read. On a
terminal it goes through the line reader: to standard output with `readline` imported, but to
standard error without it, so redirecting standard error hides it.

```python
import io
import sys

sys.stdin = io.StringIO("42\n")
sys.stdout = shown = io.StringIO()

answer = input("Answer: ")  # O(m + k)
sys.stdout = sys.__stdout__

assert shown.getvalue() == "Answer: "
assert answer == "42"
```

## Converting Input

`input()` returns text, never a number; converting it costs what the conversion costs. `float()` and
`str.split()` are linear in the text. Decimal [int()](int_func.md) is quadratic in the digits,
and refuses more digits than `sys.get_int_max_str_digits()` allows.

```python
import io
import sys

sys.stdin = io.StringIO("3.5\n5 10\n")

price = float(input())  # O(k)
assert price == 3.5

first, second = map(int, input().split())  # O(k) for short numbers
assert (first, second) == (5, 10)
```

## Reading Many Lines

Off a terminal, a loop of `input()` calls reads `n` lines in O(t) time. Each call also flushes `sys.stdout` and
`sys.stderr` and calls `sys.stdin.fileno()` to check for a terminal, so for many lines of piped
data, iterating `sys.stdin` does the same O(t) work without that per-line overhead. A loop that
stops at an empty line raises `EOFError` on input that has none, so catch `EOFError` instead.

```python
import io
import sys

sys.stdin = io.StringIO("1\n2\n3\n")

lines = []
while True:
    try:
        lines.append(input())  # O(k) per line, O(t) in all
    except EOFError:
        break
assert lines == ["1", "2", "3"]

sys.stdin = io.StringIO("1\n2\n3\n")
assert [line.rstrip("\n") for line in sys.stdin] == ["1", "2", "3"]  # O(t)
```

## Performance Best Practices

✅ **Do**:

- Iterate `sys.stdin` to read many lines of piped data
- Catch `EOFError` to detect the end of input
- Replace `sys.stdin` with an `io.StringIO` to feed `input()` in tests

❌ **Avoid**:

- Calling `input()` once per line on large piped input
- Treating an empty string as the end of input: it is an empty line

## Version Notes

- **All Python 3**: `input()` returns the line as text and never evaluates it. Python 2's
  `raw_input()` is this function.

## Related Functions

- **[open()](open.md)** - Read lines from a file
- **[sys.stdin](../stdlib/sys.md)** - The stream `input()` reads, and iterating it line by line
- **[print()](print.md)** - Write to `sys.stdout`
- **[int()](int_func.md)** - The cost of converting the text to a number
