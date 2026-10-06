# runpy Module Complexity

The `runpy` module finds a module by name or a script by path and executes its code in a fresh
namespace, the way `python -m` and `python script.py` do. Unlike `import`, it does not leave the
module it runs in `sys.modules`: every call finds, loads and executes the code again, and returns a
dictionary of the globals the code left behind.

`s` is the size of the code being run: the characters of its source when it is compiled, or of its
bytecode when a cached `.pyc` is loaded instead. `i` is the entries in `init_globals`, `g` is the
names in the globals the code leaves behind, and `f` is the import system's search for a module
name, priced on the [importlib](importlib.md) page. Every bound is `runpy`'s own cost; executing
the module's top-level statements costs whatever they do, on top.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `runpy.run_module(mod_name, init_globals=None, run_name=None, alter_sys=False)` | O(f + s + i) | O(s + i) | Imports the parent packages of a dotted name, which stay in `sys.modules`; the module itself is executed afresh on every call and is not added to it. A package runs its `__main__` submodule. Loads cached bytecode when it is current, as `import` does, and returns the namespace the code ran in |
| `runpy.run_module(mod_name, alter_sys=True)` | O(f + s + i + g) | O(s + i + g) | As above, but `sys.argv[0]` and `sys.modules[run_name]` point at the running module until it returns, and both are then restored; returns a copy of its globals |
| `runpy.run_path(path_name, init_globals=None, run_name=None)` on a file | O(s + i + g) | O(s + i + g) | A `.py` script is compiled from source on every call and no bytecode is written. Swaps and restores `sys.argv[0]` and `sys.modules[run_name]` and returns a copy of the globals, like `alter_sys=True` |
| `runpy.run_path(path_name, init_globals=None, run_name=None)` on a directory or zip file | O(f + s + i + g) | O(s + i + g) | Puts the path first on `sys.path` for the call and runs its `__main__.py` through the import system, so a directory reuses its `__pycache__`; the same swap and copy |

## Running Modules by Name

### Every Call Executes the Code Again

`run_module()` is not an import. The module runs in a new namespace each time and is not left
in `sys.modules`, so a second call pays for the code's top-level work again. Only the parent
packages of a dotted name are imported, once, the ordinary way.

```python
import pathlib
import runpy
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    (root / 'runpy_demo_pkg').mkdir()
    (root / 'runpy_demo_pkg' / '__init__.py').write_text('')
    (root / 'runpy_demo_pkg' / 'task.py').write_text('calls.append(__name__)\nresult = 42\n')
    sys.path.insert(0, tmp)
    try:
        calls = []
        first = runpy.run_module('runpy_demo_pkg.task', {'calls': calls})   # O(f + s + i)
        second = runpy.run_module('runpy_demo_pkg.task', {'calls': calls})  # executes again
        assert calls == ['runpy_demo_pkg.task', 'runpy_demo_pkg.task']
        assert first['result'] == second['result'] == 42
        assert first is not second  # a fresh namespace each time

        assert 'runpy_demo_pkg' in sys.modules           # the parent was imported
        assert 'runpy_demo_pkg.task' not in sys.modules  # the module itself was not
    finally:
        sys.path.remove(tmp)
        sys.modules.pop('runpy_demo_pkg', None)
```

### Running as `__main__`

Passing `run_name='__main__'` makes the module's `if __name__ == '__main__':` block run, which is
what `python -m` does. The module reads the command line from `sys.argv`, so set it first and put
it back afterwards.

```python
import json
import os
import runpy
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    source = os.path.join(tmp, 'in.json')
    target = os.path.join(tmp, 'out.json')
    with open(source, 'w') as f:
        f.write('{"b": 1, "a": [1, 2]}')

    saved = sys.argv
    sys.argv = ['json.tool', '--sort-keys', '--compact', source, target]
    try:
        # Equivalent to: python -m json.tool --sort-keys --compact in.json out.json
        runpy.run_module('json.tool', run_name='__main__')  # O(f + s) plus the tool's work
    finally:
        sys.argv = saved

    with open(target) as f:
        assert f.read() == '{"a":[1,2],"b":1}\n'
```

### Altering sys

With `alter_sys=True`, the running code sees its file as `sys.argv[0]` and its module under
`run_name` in `sys.modules`. Both are restored when the call returns, and the result is a copy of
the globals, O(g).

```python
import pathlib
import runpy
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    script = pathlib.Path(tmp) / 'runpy_demo_sys.py'
    script.write_text(
        'import sys\n'
        'argv0 = sys.argv[0]\n'
        'registered = getattr(sys.modules.get(__name__), "__dict__", None) is globals()\n'
        'namespace = globals()\n'
    )
    sys.path.insert(0, tmp)
    saved_argv0 = sys.argv[0]
    try:
        result = runpy.run_module('runpy_demo_sys', alter_sys=True)  # O(f + s + i + g)
        assert result['argv0'] == str(script)
        assert result['registered'] is True
        assert result['namespace'] is not result  # a copy of the globals

        plain = runpy.run_module('runpy_demo_sys')  # O(f + s + i)
        assert plain['registered'] is False
        assert plain['namespace'] is plain  # the namespace the code ran in

        assert sys.argv[0] == saved_argv0
        assert 'runpy_demo_sys' not in sys.modules
    finally:
        sys.path.remove(tmp)
```

## Running Files and Directories

### Scripts Compile on Every Call

`run_path()` on a `.py` file reads and compiles the whole source each time and never writes
bytecode, so running the same script repeatedly pays O(s) to compile it every time. A directory
holding `__main__.py` is run through the import system instead, which writes and then reuses
`__pycache__`, as `run_module()` does for a module.

```python
import os
import pathlib
import runpy
import sys
import tempfile

sys.dont_write_bytecode = False

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    script = root / 'script.py'
    script.write_text('answer = 6 * 7\n')

    result = runpy.run_path(str(script))  # O(s + i + g) - compiled from source
    assert result['answer'] == 42
    assert result['__name__'] == '<run_path>'
    assert not (root / '__pycache__').exists()  # nothing cached for next time

    app = root / 'app'
    app.mkdir()
    (app / '__main__.py').write_text('answer = 6 * 7\n')

    result = runpy.run_path(str(app), run_name='__main__')  # O(f + s + i + g)
    assert result['answer'] == 42
    assert os.listdir(app / '__pycache__')  # the next run loads bytecode
```

## Common Patterns

### Running a Script With Arguments

```python
import pathlib
import runpy
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    script = pathlib.Path(tmp) / 'greet.py'
    script.write_text(
        'import sys\n'
        'if __name__ == "__main__":\n'
        '    greeting = "Hello, " + sys.argv[1]\n'
    )

    saved = sys.argv
    sys.argv = [str(script), 'world']
    try:
        result = runpy.run_path(str(script), run_name='__main__')  # O(s + i + g)
    finally:
        sys.argv = saved

    assert result['greeting'] == 'Hello, world'
```

## Performance Best Practices

✅ **Do**:

- Import a module and call its functions when the same code runs repeatedly: `import` executes it
  once, `runpy` executes it on every call
- Use `run_module()` or a directory over `run_path()` on a `.py` file for code you run more than
  once, so the compile is paid once and cached bytecode is loaded after
- Leave `alter_sys` at its default unless the code needs `sys.argv[0]` or its own `sys.modules`
  entry; it adds a copy of the globals

❌ **Avoid**:

- `run_path()` on the same large script in a loop - every call compiles it from source
- Expecting state to persist between runs - each call starts from an empty namespace plus
  `init_globals`

## Version Notes

- **All Python 3**: `run_path()` and `run_module(..., alter_sys=True)` change `sys.argv[0]` and
  `sys.modules` for the duration of the call, so they are not thread-safe

## Related Modules

- **[importlib](importlib.md)** - The search and loading `run_module()` uses; import once instead
  of running repeatedly
- **[zipapp](zipapp.md)** - Builds the archives `run_path()` and `python archive.pyz` execute
- **[sys](sys.md)** - `sys.argv`, `sys.modules` and `sys.path`, which these functions read and
  swap
