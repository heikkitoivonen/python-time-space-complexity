# Interpreter Information Functions

Documentation for `copyright`, `credits`, and `license` - Python interpreter
information objects.

These three names are not functions and not strings. They are instances of
`_sitebuiltins._Printer`, installed into builtins by the `site` module during
interpreter startup. Displaying one calls its `__repr__`, which is why typing
the bare name in the REPL prints text.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copyright` (display) | O(n) | O(n) | 11 lines, under the limit, so the text is returned |
| `credits` (display) | O(n) | O(n) | 2 lines, under the limit |
| `license` (first display) | O(n) | O(n) | Reads and caches the LICENSE file; n = file size |
| `license` (later displays) | O(1) | O(1) | Cached, and the result is a fixed one-line hint |
| `str(obj)` / `repr(obj)` | O(n) | O(n) | n = text length, but see the line limit below |
| `obj()` (call) | O(n) | O(1) | Pages through the text, 23 lines at a time |

Two things drive the cost, and neither is obvious from the names.

**The text is loaded lazily.** `copyright` and `credits` carry their text
inline (307 and 158 characters). `license` carries filenames instead and reads
one the first time it is displayed, so only its first use is O(n) in the file.

**Display is capped at `MAXLINES` (23).** `__repr__` returns the joined text
only when the content fits in that many lines. Above it, you get a fixed
one-line hint instead. `copyright` is 11 lines and prints in full; `license` is
around 280 lines and does not.

## What These Objects Are

```python
# O(1) - attribute and type lookups
print(type(copyright))             # O(1) - <class '_sitebuiltins._Printer'>
print(isinstance(copyright, str))  # O(1) - False

# The text comes from __repr__, not from the object being a string
text = repr(copyright)             # O(n) - n = length of the text
print(len(text))                   # O(1) - 307
```

All three share the same type; they differ only in the text they carry and
where it comes from.

## Copyright Information

### `copyright` - Python Copyright

Eleven lines of text, held inline, so it prints in full.

```python
# O(n) - n = length of the embedded text
print(copyright)

# Output:
# Copyright (c) 2001-2024 Python Software Foundation.
# All Rights Reserved.
#
# Copyright (c) 2000 BeOpen.com
# All Rights Reserved.
#
# ...
```

The same text is available as the plain string `sys.copyright`, which exists
even when `site` is disabled - see [sys Module](../stdlib/sys.md).

```python
import sys

# O(n) - str() invokes __repr__ and produces the same characters
print(str(copyright) == sys.copyright)   # True
```

## Credits Information

### `credits` - Python Credits

Two lines of text, held inline.

```python
# O(n) - n = length of the embedded text
print(credits)

# Output:
#     Thanks to CWI, CNRI, BeOpen.com, Zope Corporation and a cast of thousands
#     for supporting Python development.  See www.python.org for more information.
```

There is no `sys.credits`. To get the text in code, convert the object.

```python
# O(n) - formatting invokes __repr__, n = length of the text
message = f"Credits: {credits}"

# O(n) - equivalent, and clearer about what is happening
message = "Credits: " + str(credits)
```

## License Information

### `license` - Python License

Unlike the other two, printing it does **not** show the license: at around 280
lines it exceeds the 23-line display limit, so you get a hint instead.

```python
# O(n) on first use - reads and caches the LICENSE file, then returns a hint
print(license)
# Type license() to see the full license text

# O(n) - calling it pages through the real text, 23 lines at a time
# license()   # interactive: prompts "Hit Return for more, or q ... to quit"
```

### The Lazy Read

`license` is the one object here with a cost worth knowing about. It stores
filenames rather than text and reads the file on first display - even though
the value it returns is the short hint.

```python
import time

# O(n) - first access reads roughly 280 lines from disk
start = time.perf_counter()
first = str(license)
first_us = (time.perf_counter() - start) * 1e6

# O(1) - the lines are now cached on the object
start = time.perf_counter()
second = str(license)
second_us = (time.perf_counter() - start) * 1e6

print(first == second)                             # True - both are the hint
print(f"{first_us:.0f}us then {second_us:.0f}us")  # ~1000us then ~2us
```

There is no public accessor for the cached lines, so reading the license text
in code means reading the file yourself rather than going through this object.

## Availability

All three are installed by the `site` module. Running with `-S` skips it, and
they disappear.

```python
# O(1) - membership test against the builtins namespace
import builtins

print(hasattr(builtins, "copyright"))   # O(1) - False under python -S
```

```
$ python -c "print(copyright)"      # works
$ python -S -c "print(copyright)"   # NameError: name 'copyright' is not defined
```

## Best Practices

✅ **Do**:

- Treat all three as REPL conveniences
- Use `str()` when you need the text of `copyright` or `credits`
- Call `license()` rather than printing it, if you want the actual license

❌ **Avoid**:

- Assuming these are strings - `isinstance(copyright, str)` is `False`
- Assuming they exist - they are absent under `python -S`
- Expecting `print(license)` to show the license - it prints a hint
- Importing `_Printer` - it lives in `_sitebuiltins`, is private, and you do
  not need it

## Related Functions

- [help() Function](help.md) - Interactive help, another introspection builtin
- [Exit/Quit](exit_quit.md) - The other REPL-only builtins installed by `site`
- [sys Module](../stdlib/sys.md) - `sys.copyright`, the plain-string equivalent
