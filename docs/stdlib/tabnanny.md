# tabnanny Module Complexity

The `tabnanny` module flags indentation whose meaning depends on the tab size: lines that nest
differently in editors with different tab widths. It streams each file through `tokenize` and stops at the
first problem, so a file is never held whole and at most one problem is reported per file.

`c` is the characters tokenized: up to the first problem in one file, summed over every `.py` file
in a directory walk. `l` is the characters in the longest line or multi-line token, such as a
triple-quoted string. `d` is the indentation depth, and `e` is the directory entries listed. The
bounds treat the width of one line's indentation, and the length of a path, as O(1).

## Complexity Reference

### Checking files

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tabnanny.check(file)` on a file | O(c) | O(d + l) | Any path that is not a directory is checked, whatever its suffix; a problem is printed to stdout, and `check()` returns `None` |
| `tabnanny.check(file)` on a directory | O(e + c) | O(e + d + l) | Descends every subdirectory that is not a symlink and checks each `.py` name, symlinks included; each directory's listing is held while its subdirectories are walked |
| `tabnanny.process_tokens(tokens)` | O(t) | O(d) | t = tokens taken; raises `NannyNag` at the first problem and takes no more |
| `tabnanny.verbose`, `tabnanny.filename_only` | O(1) | O(1) | Module-level switches read by `check()`; `-v` and `-q` on the command line set them |

### NannyNag

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tabnanny.NannyNag` | O(1) | O(1) | Raised by `process_tokens()`; `check()` catches it and prints it |
| `NannyNag.get_lineno()`, `NannyNag.get_msg()`, `NannyNag.get_line()` | O(1) | O(1) | Return stored attributes |

## Checking Source for Ambiguous Indentation

`check()` prints one line per file with a problem and nothing for a clean one. Read its output
rather than its return value, which is `None` either way.

```python
import contextlib
import io
import os
import tabnanny
import tempfile

with tempfile.TemporaryDirectory() as root:
    with open(os.path.join(root, 'clean.py'), 'w') as f:
        f.write('if True:\n    pass\n')
    with open(os.path.join(root, 'mixed.py'), 'w') as f:
        f.write('if True:\n\tpass\n        pass\n')  # a tab, then eight spaces

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = tabnanny.check(root)  # O(e + c) - walks the tree, streams each file

    assert result is None
    report = output.getvalue()
    assert 'mixed.py' in report and ' 3 ' in report  # the file, and the line of its problem
    assert 'clean.py' not in report

# From the command line; the exit status is 0 even when problems are printed:
# python -m tabnanny path/to/file_or_directory
```

### Checking Tokens Directly

`process_tokens()` does the same check on any token stream and raises instead of printing. It
takes tokens only until the first problem, so a file that goes wrong early is not read to the
end.

```python
import io
import tabnanny
import tokenize

source = 'if True:\n\tpass\n        pass\n' + 'x = 1\n' * 10_000
lines = io.StringIO(source)

try:
    tabnanny.process_tokens(tokenize.generate_tokens(lines.readline))  # O(t)
except tabnanny.NannyNag as nag:
    assert nag.get_lineno() == 3  # O(1)
    assert 'pass' in nag.get_line()
    assert nag.get_msg()
else:
    raise AssertionError('mixed indentation was accepted')

assert lines.tell() < 100  # stopped at line 3, not at the end
```

## Performance Best Practices

✅ **Do**:

- Point `check()` at a directory: it streams one file at a time, holding a line or token rather than a file
- Check the printed output in scripts and CI, since neither `check()` nor the exit status reports
  a problem

❌ **Avoid**:

- Expecting every problem in a file: the check stops at the first, so fix it and run again
- Calling `check()` from a long-running process on 3.12+ without catching `SystemExit` - see Version Notes

## Version Notes

- **Python 3.12+**: An I/O error opening a file, or a token or syntax error in it - indentation
  deeper than the tokenizer allows is one - prints to stderr and raises `SystemExit(1)`, which ends
  a directory walk at that file. Earlier versions print the message and carry on
- **Python 3.12+**: Indentation that raises `TabError` when compiled is reported with the
  tokenizer's `inconsistent use of tabs and spaces` message; indentation that compiles but changes
  meaning at some other tab size is still reported by `tabnanny`'s own check

## Related Modules

- **[tokenize](tokenize.md)** - the token stream `tabnanny` reads, O(c) in the source
- **[py_compile](py_compile.md)** - compiling raises `TabError` for some tab mixes, but accepts the ones only `tabnanny` flags
- **[compileall](compileall.md)** - the same directory walk, compiling instead of checking
