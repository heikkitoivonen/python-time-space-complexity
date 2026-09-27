# site Module Complexity

The `site` module runs at interpreter startup, unless Python was started with `-S`. It adds the
site-packages directories to `sys.path` and processes the `.pth` files in them. Its work is
filesystem work: it lists each site directory it processes, and checks each `.pth` path line that
names a path not already known for existence.

`P` is the entries on `sys.path` when a call starts, `e` is the entries in a site directory (every
name, not only the `.pth` files), `f` is the `.pth` files in it, `L` is the lines in those files,
`A` is the paths the call adds to `sys.path`, `c` is the characters in the largest `.pth` file,
`r` is the entries in `site.PREFIXES`, and `M` is the modules in `sys.modules`. For
`site.main()`, `e`, `f`, `L` and `A` are totals over every site directory it processes. Lines
and paths are treated as short, so one `stat` call or one path normalisation is O(1). The bounds
exclude the code an `import` line in a `.pth` file runs, and the `sitecustomize` and
`usercustomize` imports; those cost whatever their code does.

## Complexity Reference

### Site directories and .pth files

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `site.addsitedir(sitedir, known_paths=None)` | O(P + e + f log f + L) | O(P + e + A + c) | Checks every `sys.path` entry for existence first unless `known_paths` is given, lists the whole directory, and processes the `.pth` files in name order |
| `site.main()` | O(P + M + r + e + f log f + L) | O(P + M + r + e + A + c) | One `addsitedir()` per existing site directory, sharing one set of known paths; in a virtual environment its own site-packages is processed twice. `M` is paid only when a `sys.path` entry is relative, duplicated or not normalised |

### Locating site directories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `site.getsitepackages()` | O(r) | O(r) | Builds the paths from `site.PREFIXES` without checking that they exist |
| `site.getuserbase()` | O(1) | O(1) | Computed on the first call and kept in `site.USER_BASE` |
| `site.getusersitepackages()` | O(1) | O(1) | Computed on the first call and kept in `site.USER_SITE`; `main()` makes that first call at startup |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `site.PREFIXES` | O(1) | O(1) | The list `getsitepackages()` reads |
| `site.ENABLE_USER_SITE` | O(1) | O(1) | Set by `main()`: `True` when the user site directory is enabled, `None` when it is disabled for security, `False` otherwise |
| `site.USER_BASE`, `site.USER_SITE` | O(1) | O(1) | `None` until `getuserbase()` and `getusersitepackages()` fill them |

### Command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m site` | O(P) | O(1) | The printing, after startup: `sys.path` an entry at a time, then `USER_BASE` and `USER_SITE` and whether each exists. The command also pays `site.main()` twice, once at startup and once because the module runs as a script |
| `python -m site --user-base`, `python -m site --user-site` | O(1) | O(1) | The printing, after startup; the exit status is 0, 1 or 2 for `ENABLE_USER_SITE` true, false or `None`. The command also pays `site.main()` twice |

## Processing .pth Files

A `.pth` path line is joined to the site directory and added only if that path exists, so each
new one costs a `stat`. A path already known is skipped by a set lookup, not a scan of
`sys.path`. A line starting with `import` and a space or tab is executed when it is reached, so
it sees the paths the lines above it added.

```python
import os
import site
import sys
import tempfile

with tempfile.TemporaryDirectory() as sitedir:
    os.mkdir(os.path.join(sitedir, 'plugins'))
    with open(os.path.join(sitedir, 'plugins', 'marker.py'), 'w') as module:
        module.write('')
    lines = [
        '# comment lines and blank lines are skipped',
        '',
        'plugins',        # relative to sitedir, and it exists
        'missing',        # does not exist, so it is not added
        'plugins',        # already added, so it is skipped
        'import marker',  # runs when reached, and finds plugins/marker.py
    ]
    with open(os.path.join(sitedir, 'extra.pth'), 'w') as pth:
        pth.write('\n'.join(lines) + '\n')

    original = list(sys.path)
    site.addsitedir(sitedir)  # O(P + e + f log f + L)
    added = sys.path[len(original):]
    sys.path[:] = original

    real = os.path.realpath(sitedir)
    assert [os.path.realpath(path) for path in added] == [real, os.path.join(real, 'plugins')]
    assert 'marker' in sys.modules  # the import line ran
```

### The Directory Listing

`addsitedir()` lists every entry in the directory before it filters for `.pth` files, so a
site-packages directory full of installed packages costs its size even when it holds one `.pth`
file. The `.pth` files are then processed in name order, and the directories they add go to the
end of `sys.path` in that order.

```python
import os
import site
import sys
import tempfile

with tempfile.TemporaryDirectory() as sitedir:
    for name in ('b', 'a'):
        os.mkdir(os.path.join(sitedir, name))
        with open(os.path.join(sitedir, name + '.pth'), 'w') as pth:
            pth.write(name + '\n')
    for index in range(100):
        open(os.path.join(sitedir, f'package{index}.txt'), 'w').close()  # listed, then skipped

    original = list(sys.path)
    site.addsitedir(sitedir)  # O(e) to list all 104 entries, not just the two .pth files
    added = [os.path.basename(path) for path in sys.path[len(original) + 1:]]
    sys.path[:] = original

    assert added == ['a', 'b']  # a.pth sorts before b.pth
```

## Startup Cost

`site.main()` runs before your program does, at every start. It lists each site directory,
reads the `.pth` files in them, runs their `import` lines, and imports `sitecustomize`, and
`usercustomize` when the user site directory is enabled. In a virtual environment the
environment's own site-packages goes through that twice, `import` lines included. Each directory
it adds is also one more `sys.path` entry that an import miss searches; see
[`__import__()`](../builtins/__import__.md). Starting Python with `-S` skips all of it, and
`site.main()` does the same work later if a program needs it.

```python
import subprocess
import sys

script = "import sys; print('site' in sys.modules, sys.flags.no_site)"
result = subprocess.run([sys.executable, '-S', '-c', script],
                        capture_output=True, text=True, check=True)
assert result.stdout.split() == ['False', '1']  # no site directory was scanned
```

## Locating Site Directories

The lookup functions build paths from prefixes and environment variables, and none of them lists
a directory. `getsitepackages()` builds a new list on every call; the two user lookups compute
their path once and keep it.

```python
import site

packages = site.getsitepackages()  # O(r) - paths built from site.PREFIXES
assert all(isinstance(path, str) for path in packages)
assert site.getsitepackages() is not packages  # a new list on every call

user_site = site.getusersitepackages()  # O(1) - cached after the first call
assert user_site is site.USER_SITE
assert site.getuserbase() is site.USER_BASE  # O(1)
```

## Performance Best Practices

✅ **Do**:

- Keep `.pth` `import` lines few and cheap: they run at every interpreter start
- Start short-lived scripts that need no installed packages with `-S`, which skips the site
  directory scans
- Use `sys.path.append()` for a directory that holds no `.pth` files; `addsitedir()` also lists
  it and checks every `sys.path` entry first

❌ **Avoid**:

- Adding many directories through `.pth` files: each one lengthens the path an import miss
  searches
- Heavy work in `sitecustomize` or `usercustomize`, which are imported at every start

## Version Notes

- **Python 3.12.4+**: `.pth` files are read whole, which is the `c` term, and decoded as UTF-8, a
  byte order mark accepted, falling back to the locale encoding; earlier releases read them a line
  at a time in the locale encoding

## Related Modules

- **[sys](sys.md)** - what an entry on `sys.path` costs to add, find and search
- **[sysconfig](sysconfig.md)** - the installation schemes behind the site-packages paths
- **[venv](venv.md)** - the `pyvenv.cfg` that `site` reads at startup to pick the site directories
