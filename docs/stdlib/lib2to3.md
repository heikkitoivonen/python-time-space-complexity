# lib2to3 Module Complexity

The `lib2to3` module is the library behind the `2to3` tool, which rewrites Python 2 source as
Python 3. It parses one file at a time into a lossless syntax tree with its own LL(1) parser, runs
a set of *fixers* over that tree, and prints the tree back as source. It is pure Python, and the
whole file and its tree are in memory while that file is processed.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13. The page covers the module as it is on
    Python 3.10 to 3.12, and its examples run only there. The official documentation calls every
    interface except the `2to3` command unstable; the classes below are the ones that command is
    built from. The grammar is Python 2's plus the Python 3 syntax of 3.8 and earlier, so a
    `match` statement is a parse error.

Tokens are the unit throughout. `n` is the tokens in one source file; in the space of a call that
handles several files, it is the largest one. `t` is the files and directories a call is given or
walks, `f` is the fixers loaded, and `m` is the candidate nodes handed to the busiest fixer: the
nodes shaped like what it rewrites, whether or not they need it. `d` is the depth of the tree,
small for ordinary code; a deeply nested expression multiplies every walk over the tree by it, and
nesting deep enough raises `RecursionError`. The fixer set is fixed once a tool is built, and each
fixer's work on one candidate is treated as O(1).

## Complexity Reference

### Command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `2to3 [options] file_or_dir ...`, `python -m lib2to3 [options] file_or_dir ...` | O(f) + O(n·d + m²) per file, plus the diff | O(n + t) per process | Prints a `difflib` unified diff of each changed file, priced on that page, and writes nothing; `-w` writes back, keeping a `.bak` copy unless `-n` is given |
| `lib2to3.main.main(fixer_pkg, args=None)` | O(f) + O(n·d + m²) per file, plus the diff | O(n + t) per process | What the command runs; returns 0, or 1 when any file could not be read, parsed or written; `-j N` spreads files over N processes |

### RefactoringTool

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `refactor.get_fixers_from_package(pkg_name)` | O(f) | O(f) | Dotted names of the package's `fix_*` modules |
| `refactor.RefactoringTool(fixer_names, options=None, explicit=None)` | O(f) | O(f) | Imports and builds each fixer and compiles its pattern; an explicit-only fixer is skipped unless named in `explicit` |
| `RefactoringTool.refactor_string(data, name)` | O(n·d + m²) | O(n) | Returns the rewritten tree; a parse error raises |
| `RefactoringTool.refactor_file(filename, write=False, doctests_only=False)` | O(n·d + m²) | O(n) | Reads the whole file; writes only with `write=True` and only if something changed |
| `RefactoringTool.refactor_dir(dir_name, write=False, doctests_only=False)` | O(n·d + m²) per file | O(n + t) | Every `.py` file under the directory; names starting with `.` are skipped, directories included |
| `RefactoringTool.refactor(items, write=False, doctests_only=False)` | O(n·d + m²) per file | O(n + t) | `refactor_dir()` or `refactor_file()` for each item |
| `RefactoringTool.refactor_docstring(input, filename)` | O(n·d + m²) | O(n) | Parses only the `>>>` examples and returns the rewritten text |
| `RefactoringTool.refactor_tree(tree, name)` | O(n·d + m²) | O(n) | Rewrites the tree in place; returns whether the tree has been changed |
| `RefactoringTool.files`, `RefactoringTool.wrote` | O(1) | O(1) | The files found to need changes, and whether any were written |
| `refactor.FixerError` | O(1) | O(1) | Raised when a fixer module has no matching `Fix...` class |

### Syntax trees

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `driver.Driver(grammar, convert=None, logger=None)`, `Driver.parse_string(text)` | O(n) | O(n) | Parsing alone, no fixers; pass `pygram.python_grammar` and `convert=pytree.convert` for the tree the fixers work on |
| `str(tree)` | O(n·d) | O(n) | Comments and whitespace are part of the tree, so unchanged code comes back byte for byte |
| `Base.pre_order()`, `Base.post_order()`, `Base.leaves()` | O(n·d) to exhaust | O(d) | Lazy generators, nested one per level |

## Converting Source

### Refactoring a String

`refactor_string()` parses the whole string, runs every fixer, and hands back the tree; `str()` of
the tree is the new source. Comments and spacing survive, because they are stored in the tree
alongside the tokens.

```python
from lib2to3 import refactor

fixers = refactor.get_fixers_from_package('lib2to3.fixes')  # O(f)
tool = refactor.RefactoringTool(fixers)  # O(f) - built once, reused for every file

source = "print 'total:', d.has_key(k)  # keep me\n"
tree = tool.refactor_string(source, '<example>')  # O(n·d + m²)
assert str(tree) == "print('total:', k in d)  # keep me\n"  # O(n·d)
assert tree.was_changed
```

### Choosing Fixers

The tool runs exactly the fixers it is built with. A few are explicit-only and are skipped unless
`explicit` names them, and the `print_function` option is how code that already calls `print()`
with keyword arguments gets past the parser.

```python
from lib2to3 import refactor
from lib2to3.pgen2.parse import ParseError

idioms = 'lib2to3.fixes.fix_idioms'
skipped = refactor.RefactoringTool([idioms])
assert skipped.pre_order == skipped.post_order == []  # explicit-only: not loaded
tool = refactor.RefactoringTool([idioms], explicit=[idioms])
assert str(tool.refactor_string("if type(x) == int: pass\n", 'idioms')) == (
    "if isinstance(x, int): pass\n"
)

modern = "print('a', end='')\n"
try:
    refactor.RefactoringTool(['lib2to3.fixes.fix_print']).refactor_string(modern, 'm')
except ParseError:
    pass  # without the option, print is a statement keyword
else:
    raise AssertionError('print() with a keyword argument parsed as a statement')

tool = refactor.RefactoringTool(['lib2to3.fixes.fix_print'], {'print_function': True})
assert str(tool.refactor_string(modern, 'm')) == modern
```

### Files and Directories

`refactor_dir()` walks the directory with `os.walk` and refactors each `.py` file in turn, so
memory holds the largest file's tree and a list of names, not every tree. Nothing is written unless `write=True`, and a file with
nothing to change is not rewritten.

```python
import os
import tempfile
from lib2to3 import refactor

tool = refactor.RefactoringTool(['lib2to3.fixes.fix_print'])

with tempfile.TemporaryDirectory() as directory:
    def path(*parts):
        return os.path.join(directory, *parts)

    os.mkdir(path('.cache'))
    for name in ('old.py', 'new.py', os.path.join('.cache', 'skipped.py')):
        with open(path(name), 'w') as f:
            f.write("print 'x'\n" if name != 'new.py' else "print('x')\n")

    tool.refactor_dir(directory, write=True)  # O(n·d + m²) per file
    assert tool.files == [path('old.py')]  # only the file that needed changes
    with open(path('old.py')) as f:
        assert f.read() == "print('x')\n"
    with open(path('.cache', 'skipped.py')) as f:
        assert f.read() == "print 'x'\n"  # names starting with '.' are skipped
```

## Parse Errors

A `RefactoringTool` raises on the first file it cannot parse. The `2to3` command logs the error
instead, carries on with the remaining files, and returns 1. Python 3 syntax newer than 3.8 is
one way to get there.

```python
from lib2to3 import refactor
from lib2to3.pgen2.parse import ParseError

tool = refactor.RefactoringTool(refactor.get_fixers_from_package('lib2to3.fixes'))

assert str(tool.refactor_string("if (y := 1): pass\n", 'walrus')) == "if (y := 1): pass\n"

try:
    tool.refactor_string("match x:\n    case 1:\n        pass\n", 'match')
except ParseError as error:
    assert 'bad input' in str(error)
else:
    raise AssertionError('a match statement parsed')
```

## Using the 2to3 Command

The command prints a diff for every file it would change and leaves the files alone. `-w` writes
the changes back, `-n` skips the `.bak` copies, and `-j N` refactors N files at a time in
separate processes.

```bash
# Python 3.10 to 3.12
2to3 script.py                 # Show the diff only
2to3 -w script.py              # Write back, keeping script.py.bak
2to3 -w -n src/                # Write back a whole tree, no backups
2to3 -f print -f has_key src/  # Run only these two fixers
2to3 -x print src/             # Run every default fixer except print
2to3 -n -W -o out/ src/        # Write every file, converted or not, under out/
2to3 -d README.rst             # Refactor only the doctests
2to3 -l                        # List the fixers
```

The same, run from Python:

```python
import os
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as directory:
    script = os.path.join(directory, 'script.py')
    with open(script, 'w') as f:
        f.write("print 'hello'\n")

    shown = subprocess.run([sys.executable, '-m', 'lib2to3', script],
                           capture_output=True, text=True)
    assert shown.returncode == 0
    assert "+print('hello')" in shown.stdout
    with open(script) as f:
        assert f.read() == "print 'hello'\n"  # a diff only: nothing written

    subprocess.run([sys.executable, '-m', 'lib2to3', '-w', script],
                   capture_output=True, check=True)
    with open(script) as f:
        assert f.read() == "print('hello')\n"
    assert os.path.exists(script + '.bak')
```

## Performance Best Practices

✅ **Do**:

- Build one `RefactoringTool` and reuse it; construction imports and compiles every fixer
- Use `-j N` on a large tree; files are independent, so they spread across processes
- Split a generated file with very many candidates for one fixer into several; the match loop
  is quadratic in them within one file

❌ **Avoid**:

- `lib2to3` on new code - it cannot parse syntax newer than Python 3.8, and the module is gone
  from 3.13

## Version Notes

- **Python 3.11+**: `import lib2to3` emits `DeprecationWarning`, where 3.10 emits
  `PendingDeprecationWarning`
- **Python 3.13+**: The module and the `2to3` command are removed; `import lib2to3` raises
  `ModuleNotFoundError`

## Related Modules

- **[ast](ast.md)** - Parses every syntax of the running Python; drops comments and spacing
- **[tokenize](tokenize.md)** - The tokens with exact positions, for edits that keep the
  original formatting
- **[difflib](difflib.md)** - Builds the unified diff `2to3` prints for each changed file
