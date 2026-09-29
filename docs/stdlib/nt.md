# nt Module Complexity

The `nt` module is the C module beneath `os` on Windows, and exists only there: the same source
that is built as [`posix`](posix.md) on Unix. `os` imports its functions into its own namespace,
so every public function `nt` exposes is the object `os` exposes under the same name, and its
bounds are on the [os page](os.md). What `os` adds in Python - `walk()`, `makedirs()`,
`fdopen()`, `getenv()`, the `execl*()` and `spawnl*()` wrappers, `add_dll_directory()` - is not
in `nt` at all.

Two things are `nt`'s own. `nt.environ` is a copy of the environment that, unlike
`posix.environ`, is not the storage behind `os.environ`. And a set of private helpers carries
`ntpath`'s work on Windows; what each path function costs with them, and without them, is on the
[ntpath page](ntpath.md).

`L` is the length of a path argument in characters, `C` the length of the working directory,
and `F` the length of the final path `_getfinalpathname()` returns. For the environment, `b` is
the characters of every variable, keys and values together, `n` the characters of the keys
alone, `k` is a key's length and `v` a value's. A system call counts as O(1), as it does on the
os page.

## Complexity Reference

### Functions shared with os

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nt.open()`, `nt.read()`, `nt.stat()`, `nt.listdir()`, ... | as `os` | as `os` | The same function objects `os` exposes, not wrappers; see the [os page](os.md) for each bound |
| `nt.getcwd()`, `nt.getcwdb()` | O(C) | O(C) | The whole working directory is copied into the result |
| `nt.uname_result` | O(1) | O(1) | The class `os.uname_result`; `nt` has no `uname()`, so nothing on Windows builds one |
| `nt.uname_result.n_fields`, `nt.uname_result.n_sequence_fields`, `nt.uname_result.n_unnamed_fields` | O(1) | O(1) | Class attributes of the struct sequence |

### times_result

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nt.times_result` | O(1) | O(1) | The class `os.times()` returns |
| `nt.times_result.user`, `nt.times_result.system` | O(1) | O(1) | CPU seconds this process has used |
| `nt.times_result.children_user`, `nt.times_result.children_system`, `nt.times_result.elapsed` | O(1) | O(1) | Always `0` on Windows, which does not report them |
| `nt.times_result.n_fields`, `nt.times_result.n_sequence_fields`, `nt.times_result.n_unnamed_fields` | O(1) | O(1) | Class attributes of the struct sequence |

### environ

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nt.environ` (built at startup) | O(b) | O(b) | A plain `dict` of `str` keys and values, copied once from the C runtime's environment; keys keep the case they were set with |
| `nt.environ[key]` | O(k) | O(1) | A `dict` lookup, so it is case-sensitive where Windows is not; returns the stored object |
| `os.environ` (built at import) | O(n) | O(n) | A second `dict`: every key of `nt.environ` upper-cased into a new string, and each value the object `nt.environ` holds, not a copy |
| `os.environ[key]` | O(k) | O(k) | Upper-cases the key, so any case finds it, then returns the stored value itself |
| `os.environ[key] = value` | O(k + v) | O(k + v) | Stores into `os.environ`'s own dict and calls `putenv()`; `nt.environ` does not change |
| `os.reload_environ()` | O(b) | O(b) | 3.14+; rebuilds `os.environ`'s dict from `nt._create_environ()` and leaves `nt.environ` as it was |

### Private helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `nt._path_isdir(path)`, `nt._path_isfile(path)`, `nt._path_islink(path)`, `nt._path_exists(path)` | O(1) | O(1) | 3.12+; these are `ntpath.isdir()`, `isfile()`, `islink()` and `exists()`. Through 3.11 those four are built on `os.stat()` and `os.lstat()`, O(1) as well |
| `nt._path_isjunction(path)`, `nt._path_lexists(path)` | O(1) | O(1) | 3.13+; these are `ntpath.isjunction()` and `ntpath.lexists()` |
| `nt._path_isdevdrive(path)` | O(1) | O(1) | 3.12+; `ntpath.isdevdrive()` calls it after an `abspath()` |
| `nt._path_normpath(path)` | O(L) | O(L) | 3.11+; one pass, and what `ntpath.normpath()` runs on Windows; see [ntpath](ntpath.md) |
| `nt._path_splitroot_ex(path)` | O(L) | O(L) | 3.13+; this is `ntpath.splitroot()` |
| `nt._path_splitroot(path)` | O(L) | O(L) | `(root, rest)`, for `importlib`'s path handling |
| `nt._getfullpathname(path)` | O(L + C) | O(L + C) | `ntpath.abspath()`'s one call; a relative path is resolved against the working directory |
| `nt._getvolumepathname(path)` | O(L) | O(L) | The mount point that contains `path` |
| `nt._getfinalpathname(path)` | O(F) | O(F) | Opens the path and asks for its final name, every link resolved in that one call |
| `nt._findfirstfile(path)` | O(1) | O(1) | 3.13+; a file name as it is spelled on disk, read from its directory without opening it |
| `nt._getdiskusage(path)` | O(1) | O(1) | `(total, free)` for `shutil.disk_usage()` |
| `nt._add_dll_directory(path)`, `nt._remove_dll_directory(cookie)` | O(1) | O(1) | Behind `os.add_dll_directory()` and the handle it returns |
| `nt._create_environ()` | O(b) | O(b) | 3.14+; a fresh `dict` of the process environment |
| `nt._exit(n)` | O(1) | O(1) | This is `os._exit()` |
| `nt._have_functions`, `nt._LOAD_LIBRARY_SEARCH_*` | O(1) | O(1) | A list `os` reads at import to build its `supports_*` sets, and flags `ctypes` passes when it loads a DLL |
| `nt._supports_virtual_terminal()`, `nt._is_inputhook_installed()`, `nt._inputhook()` | O(1) | O(1) | 3.13+; for the REPL and coloured output. `_inputhook()` runs whatever hook is installed, at that hook's cost |

## The Functions Are os's Functions

`os` does not wrap `nt`; on Windows it imports the C module's functions into its own namespace.
There is no portability layer between the two to pay for, and a bound established for
`os.read()` is the bound of `nt.read()`.

```python
import nt
import os

assert nt.open is os.open  # the same function object, so the same cost
assert nt.stat is os.stat
assert nt.getcwd is os.getcwd  # O(C) - the result is the whole working directory

assert not hasattr(nt, "walk")  # os.walk() is Python that os adds
assert nt.environ is not os.environ  # the one public name the two modules do not share
```

## Two Environment Dicts

On Unix, `os.environ` stores into `posix.environ`. On Windows it cannot: environment names are
case-insensitive there, so `os.environ` keeps its own dict with every key upper-cased, and
upper-cases each key it is asked for. Building that dict copies the keys only: the values are
the string objects `nt.environ` already holds. `nt.environ` is left as the copy taken at startup, with
names in their original case, and nothing in `os` writes to it afterwards.

```python
import nt
import os

os.environ["Nt_Page_Greeting"] = "hello"  # O(k + v): upper-case, store, putenv()

assert os.environ["NT_PAGE_GREETING"] == "hello"  # O(k) - any case finds it
assert os.environ["nt_page_greeting"] is os.environ["NT_PAGE_GREETING"]  # the stored object

assert "Nt_Page_Greeting" not in nt.environ  # the startup copy, which nothing updates
```

Reading `nt.environ` therefore answers with the environment as it was when the process started,
and only for a name spelled the way it was set. `os.environ` is current and matches any case.

## Performance Best Practices

✅ **Do**:

- Call `os` and `ntpath`, not `nt`: the functions are the same objects, and the private helpers
  change from release to release
- Read the environment through `os.environ`, which is current and matches a name in any case

❌ **Avoid**:

- `nt.environ` for a lookup - it is the startup snapshot, case-sensitive, and `os` never updates
  it

## Version Notes

- **Python 3.14+**: `os.reload_environ()` rebuilds `os.environ` from `nt._create_environ()`;
  `nt.environ` is still the startup copy
- **All Python 3**: Windows only. On other platforms `import nt` raises `ModuleNotFoundError`

## Related Modules

- **[os](os.md)** - the portable interface, and the bounds of every function here
- **[posix](posix.md)** - the same C module on Unix, whose `environ` is `os.environ`'s storage
- **[ntpath](ntpath.md)** - Windows path operations, and what they cost with and without the
  helpers above
- **[pathlib](pathlib.md)** - object-oriented paths over the same calls
