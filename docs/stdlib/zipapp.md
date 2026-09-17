# zipapp Module Complexity

The `zipapp` module packs a directory into a ZIP archive the interpreter can
run, and copies such archives with a new shebang line. Three costs are worth
separating.

Building from a directory copies every byte of every file under it and touches
every entry, directories included. Nothing is excluded by default, and the
`filter` callback decides inclusion one entry at a time without pruning: a
rejected directory is still walked and its contents are still offered.

Copying an existing archive streams its bytes after the shebang line and never
parses the archive. Reading the interpreter back reads one line.

Running the result is a different module's cost. `zipimport` reads the central
directory, then compiles every `.py` member it imports on every start,
because nothing is written back into the archive. Packing `.pyc` members
beside the sources removes that compile.

## Complexity Reference

Size variables: f = entries under the source directory, files and directories
both, before `filter` sees them; b = bytes in the files packed; a = bytes in
an existing archive; s = bytes in a shebang line, the one written or the one
replaced; c = the cost of one `filter` call.

### Building an archive

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `create_archive(directory, target=None, ...)` | O(b + f) | O(f) | Walks every entry under the directory and writes each one as a member, directories included. Contents stream through a fixed buffer; the O(f) is the member list held for the central directory. 3.14 sorts the listing before writing, an extra O(f log f) |
| `filter=func` | O(f·c) | O(1) | Called once per entry with its path relative to the source. A rejected directory is not pruned: its contents are still walked and still offered |
| `compressed=True` | O(b) | O(1) | Deflates each member instead of storing it. The loader inflates a member each time it reads it |
| `main='mod:fn'` | O(1) | O(1) | Writes a three-line `__main__.py`. Refused when the directory already has one, and required when it does not |
| `interpreter=path` | O(s) | O(s) | Writes the shebang ahead of the archive and sets the executable bit on a path target |
| `ZipAppError` | — | — | A `ValueError`, raised before the target is opened, so a refused build writes nothing |

Up to 3.13 the directory is walked while the target is being written, so a
target inside the source directory becomes a member of itself. 3.14 lists the
entries before opening the target, and raises `ZipAppError` when a target that
already exists is among them.

### Copying and inspecting an archive

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `create_archive(archive, target, interpreter=None)` | O(a + s) | O(s) | Skips the source's shebang line and streams the rest without parsing it. `interpreter=None` drops the shebang rather than keeping it. The executable bit is set for a `str` target only, not a `pathlib.Path` |
| `get_interpreter(archive)` | O(s) | O(s) | Reads two bytes, and the rest of the line only when they are `#!`. `None` when there is no shebang |
| `python -m zipapp` | as `create_archive()` | as `create_archive()` | `--info` is `get_interpreter()`. Copying an archive onto itself, or with `-m`, is refused |

### Running an archive

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python app.pyz` | O(m) + members imported | O(m) + members imported | m = members; reading the central directory is O(m). Each `.py` member imported is compiled at every start. A `.pyc` member beside it that still matches the source is used instead |

## The filter prunes nothing

`filter` is asked about every entry under the source, so excluding a directory
means rejecting every path beneath it, not just the directory itself. Rejecting
the directory alone still packs its contents.

```python
import tempfile
import zipapp
import zipfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / "app"
    (source / "pkg" / "__pycache__").mkdir(parents=True)
    (source / "pkg" / "__init__.py").write_text("def main():\n    print('hi')\n")
    (source / "pkg" / "__pycache__" / "stale.pyc").write_bytes(b"")

    seen = []

    def keep(path):
        seen.append(path.as_posix())  # called once per entry - O(f) calls
        return "__pycache__" not in path.parts  # reject the whole subtree

    # Build - O(b + f)
    zipapp.create_archive(source, Path(tmp) / "app.pyz", main="pkg:main", filter=keep)

    # The directory was rejected, and its contents were still offered
    offered = ["pkg", "pkg/__init__.py", "pkg/__pycache__", "pkg/__pycache__/stale.pyc"]
    assert sorted(seen) == offered

    names = zipfile.ZipFile(Path(tmp) / "app.pyz").namelist()
    assert sorted(names) == ["__main__.py", "pkg/", "pkg/__init__.py"]
```

## Copying an archive never parses it

Giving an existing archive as the source replaces its shebang line and copies
the rest byte for byte. The archive is not parsed, so the copy costs its size
and nothing more, and a file that is not a ZIP archive at all is copied just as
readily. Pass the target as a `str` when the copy should be executable.

```python
import os
import tempfile
import zipapp
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / "app"
    source.mkdir()
    (source / "__main__.py").write_text("print('hi')\n")

    built = Path(tmp) / "app.pyz"
    zipapp.create_archive(source, built)  # no shebang
    assert zipapp.get_interpreter(built) is None  # reads two bytes - O(1)

    # Copy with a shebang - O(a) in the archive's size
    shipped = os.path.join(tmp, "app-shipped.pyz")
    zipapp.create_archive(built, shipped, interpreter="/usr/bin/env python3")
    assert zipapp.get_interpreter(shipped) == "/usr/bin/env python3"  # one line - O(s)
    assert built.stat().st_size + len(b"#!/usr/bin/env python3\n") == os.stat(shipped).st_size

    # Copy again without an interpreter: the shebang is dropped, not kept
    plain = Path(tmp) / "app-plain.pyz"
    zipapp.create_archive(shipped, plain)
    assert zipapp.get_interpreter(plain) is None
    assert plain.read_bytes() == built.read_bytes()
```

## Ship bytecode, or pay the compile at every start

`zipimport` never writes bytecode back into the archive, and ignores a
`__pycache__` directory packed inside it, so a `.py` member is compiled each
time the application starts. What it does look for is a `.pyc` beside the
source, which `compileall.compile_dir()` writes with `legacy=True`, and it uses
that whenever it still matches the source. Compile once, then pack.

```python
import compileall
import tempfile
import zipapp
import zipfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / "app"
    (source / "pkg").mkdir(parents=True)
    (source / "pkg" / "__init__.py").write_text("def main():\n    print('hi')\n")

    # Compile once, at build time - O(source length)
    compileall.compile_dir(source, legacy=True, quiet=1)

    # Pack sources and bytecode together - O(b + f)
    zipapp.create_archive(source, Path(tmp) / "app.pyz", main="pkg:main")

    names = zipfile.ZipFile(Path(tmp) / "app.pyz").namelist()
    assert "pkg/__init__.pyc" in names
    # Running it: python app.pyz imports pkg from the .pyc, and compiles only
    # the three-line __main__.py that main= generated
```

The command line does the same work as `create_archive()`:

```bash
# Build from a directory - O(b + f)
python -m zipapp app -m pkg:main -o app.pyz

# Copy with a shebang - O(a); the copy is made executable
python -m zipapp app.pyz -p "/usr/bin/env python3" -o app-shipped.pyz

# Read the shebang back - O(s)
python -m zipapp app-shipped.pyz --info
```

## Related Documentation

- [zipfile Module](zipfile.md)
- [zipimport Module](zipimport.md)
- [compileall Module](compileall.md)
- [runpy Module](runpy.md)
