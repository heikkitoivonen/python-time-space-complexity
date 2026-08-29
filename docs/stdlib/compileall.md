# compileall Module

The `compileall` module compiles all Python source files in a directory tree to bytecode (.pyc files).

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compile_dir()` | O(E + B) | O(E) | E = every directory entry examined, not just `.py` files; B = source bytes compiled. Both terms measured on CPython 3.11, one Linux machine, tmpfs - illustrative: adding 5000 non-Python files to a directory of 20 modules made it 10.9x slower, and 200 ten-line files cost about nine times 10 two-hundred-line files |
| `compile_file()` | O(m) | O(m) | m = file size; one file |
| `workers=N` | - | O(N * working set) | Each process holds its own source and compiler state |
| `compile_path()` | O(E + B) | O(E) | Same walk, over the entries of each `sys.path` directory |
| `main()` | O(E + B) | O(E) | CLI entrypoint |

## Batch Compiling Python Files

### Compile Directory

```python
import compileall
import tempfile
from pathlib import Path

tree = Path(tempfile.mkdtemp())
(tree / 'example.py').write_text('value = 1\n')

# Compile directory tree - O(n + total bytes)
compileall.compile_dir(tree)

# With options
compileall.compile_dir(
    tree,
    force=True,        # Recompile all
    quiet=0            # Show progress
)

# workers=N compiles files in parallel (workers=0 uses one per CPU)
compileall.compile_dir(tree, workers=4, quiet=1)

# Or from command line:
# python -m compileall /path/to/code
```

!!! warning "The return value only reports compilation failures"

    `compile_dir()` returns `False` when a file fails to compile, and `True`
    otherwise - including when it could not read the directory at all. A path
    that does not exist, or that is a file rather than a directory, is
    reported as success.

```python
import compileall
import tempfile
from pathlib import Path

tree = Path(tempfile.mkdtemp())
(tree / 'broken.py').write_text('def (\n')

compileall.compile_dir(tree, quiet=2)               # False - a real failure
compileall.compile_dir(tree / 'nowhere', quiet=2)   # True, despite listing nothing
compileall.compile_dir(tree / 'broken.py', quiet=2)  # True, and it is not a directory

# So check the path yourself before trusting the result
def compile_tree(path):
    if not path.is_dir():
        raise NotADirectoryError(path)
    return compileall.compile_dir(path, quiet=2)

print(compile_tree(tree))  # False - broken.py is still in there
```

### Compile Single File

```python
import py_compile
import tempfile
from pathlib import Path

source = Path(tempfile.mkdtemp()) / 'myfile.py'
source.write_text('value = 1\n')

# Compile one file - O(m) in the file's size
py_compile.compile(source)

# A missing file raises rather than returning None - doraise only controls
# what happens to compilation errors, not to reading the source
try:
    py_compile.compile(source.with_name('absent.py'))
except FileNotFoundError as error:
    print(f'no such source: {error.filename}')
```

## Related Documentation

- [py_compile Module](py_compile.md)
- [ast Module](ast.md)
