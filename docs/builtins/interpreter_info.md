# Interpreter Information Functions

Documentation for `copyright`, `credits`, and `license` - Python interpreter
information objects.

These three names are not functions and not strings. They are instances of
`_sitebuiltins._Printer`, installed into builtins by the `site` module during
interpreter startup. Displaying one calls its `__repr__`, which is why typing
the bare name in the REPL prints text.

`n` is the characters in the object's text: the inline text for `copyright`
and `credits`, and the license file for `license`.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `copyright` (display) | O(n) | O(n) | 11 lines, under the limit, so the text is returned |
| `credits` (display) | O(n) | O(n) | A few lines, under the limit |
| `license` (first display) | O(n) | O(n) | Reads and caches the license file |
| `license` (later displays) | O(1) | O(1) | Cached, and the result for the interpreter's license file is a fixed one-line hint |
| `str(obj)` / `repr(obj)` | O(n) | O(n) | But see the line limit below |
| `obj()` (call) | O(n) | O(n) | A first use loads the text as display does; the whole text then goes to a pager. Before 3.13.12 and 3.14.3: O(1) space once cached, printing 23 lines at a time |

Two things drive the cost, and neither is obvious from the names.

**The text is loaded lazily.** `copyright` and `credits` carry their text
inline. `license` carries filenames instead and reads one the first time it is
displayed, so only its first use is O(n) in the file.

**Display is capped at `MAXLINES` (23).** `__repr__` returns the joined text
only when the content fits in that many lines. Above it, you get a fixed
one-line hint instead. `copyright` is 11 lines and prints in full; the license
file runs to a few hundred lines and does not.

## What These Objects Are

```python
import sys

# O(1) - attribute and type lookups
assert type(copyright).__name__ == "_Printer"
assert not isinstance(copyright, str)
assert type(credits) is type(license) is type(copyright)

# The text comes from __repr__, not from the object being a string
text = repr(copyright)             # O(n) - n = length of the text
assert text == sys.copyright
```

All three share the same type; they differ only in the text they carry and
where it comes from.

## Copyright Information

### `copyright` - Python Copyright

Eleven lines of text, held inline, so it prints in full.

```python
# O(n) - n = length of the embedded text
text = str(copyright)

assert text.count("\n") + 1 == 11
assert text.startswith("Copyright (c) 2001")
assert "Python Software Foundation" in text
```

The same text is available as the plain string `sys.copyright`, which exists
even when `site` is disabled - see [sys Module](../stdlib/sys.md).

```python
import sys

# O(n) - str() invokes __repr__ and produces the same characters
assert str(copyright) == sys.copyright
```

## Credits Information

### `credits` - Python Credits

A few lines of text, held inline.

```python
# O(n) - n = length of the embedded text
text = str(credits)

assert text.lstrip().startswith("Thanks to CWI, CNRI, BeOpen")
assert "www.python.org" in text
```

There is no `sys.credits`. To get the text in code, convert the object.

```python
import sys

assert not hasattr(sys, "credits")

# O(n) - formatting invokes __repr__, n = length of the text
message = f"Credits: {credits}"

# O(n) - equivalent, and clearer about what is happening
assert message == "Credits: " + str(credits)
```

## License Information

### `license` - Python License

Unlike the other two, printing it does **not** show the license: the license
file exceeds the 23-line display limit, so you get a hint instead. If the
interpreter's own license file is missing, it shows what it finds instead: a
`LICENSE.txt` or `LICENSE` in the current directory, or failing that a
one-line pointer to `https://www.python.org/psf/license/`, which prints in
full.

```python
# O(n) on first use - reads and caches the license file, then returns a hint
text = str(license)  # run where the current directory has no LICENSE file
assert text in (
    "Type license() to see the full license text",
    "See https://www.python.org/psf/license/",
)

# O(n) - calling it pages through the real text
# license()   # interactive: waits for input between pages
```

### The Lazy Read

`license` is the one object here with a cost worth knowing about. It stores
filenames rather than text and reads the file on first display - even though
the value it returns is the short hint. An audit hook shows the files being
opened on the first display and not on the second.

```python
import sys

opened = []
sys.addaudithook(lambda event, args: event == "open" and opened.append(args[0]))

first = str(license)     # O(n) - opens and reads the license file
reads_on_first = len(opened)

second = str(license)    # O(1) - the lines are now cached on the object

assert first == second
assert reads_on_first > 0
assert len(opened) == reads_on_first
```

There is no public accessor for the cached lines, so reading the license text
in code means reading the file yourself rather than going through this object.

## Availability

All three are installed by the `site` module. Running with `-S` skips it, and
they disappear.

```python
import builtins
import sys

# O(1) - membership test against the builtins namespace
assert hasattr(builtins, "copyright") == (not sys.flags.no_site)
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

## Version Notes

- **Python 3.13.12+, 3.14.3+ and 3.15**: calling one of these objects joins
  the whole text and hands it to a pager (such as `less` on a terminal)
  instead of printing 23 lines at a time and prompting "Hit Return for more,
  or q (and Return) to quit"

## Related Functions

- [help() Function](help.md) - Interactive help, another introspection builtin
- [Exit/Quit](exit_quit.md) - The other REPL-only builtins installed by `site`
- [sys Module](../stdlib/sys.md) - `sys.copyright`, the plain-string equivalent
