# winreg Module Complexity

The `winreg` module exposes the Windows registry: keys that hold subkeys and named values,
reached through handles. Every function is one or two registry calls with argument conversion
around them. The module caches nothing, so the next call goes back to the registry.

It is Windows-only. On other platforms `import winreg` raises `ModuleNotFoundError`.

A registry call counts as O(1) here, the way a syscall does on the [os](os.md) page. Where the
work scales with an argument, the row says so. `n` is the bytes of the value data being read or
written (two per character for the string types, which are UTF-16). `M` is the bytes of the
largest value in the key, name and data together. `k` is a key's subkeys and `v` its values.
`s` and `x` are the characters in a string passed to `ExpandEnvironmentStrings()` and in its
result.

## Complexity Reference

### Keys

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winreg.OpenKey(key, sub_key, reserved=0, access=KEY_READ)`, `winreg.OpenKeyEx(...)` | O(1) | O(1) | Two names for the same call; returns a new handle |
| `winreg.CreateKey(key, sub_key)` | O(1) | O(1) | Opens the key if it already exists |
| `winreg.CreateKeyEx(key, sub_key, reserved=0, access=KEY_WRITE)` | O(1) | O(1) | `CreateKey()` with explicit access rights |
| `winreg.CloseKey(hkey)` | O(1) | O(1) | Same as `PyHKEY.Close()`; also accepts a raw integer handle |
| `winreg.DeleteKey(key, sub_key)` | O(1) | O(1) | Its values go with it; a key that still has subkeys raises `PermissionError` |
| `winreg.DeleteKeyEx(key, sub_key, access=KEY_WOW64_64KEY, reserved=0)` | O(1) | O(1) | `DeleteKey()` in a chosen 32- or 64-bit registry view |
| `winreg.QueryInfoKey(key)` | O(1) | O(1) | `(subkeys, values, last_modified)`; the counts come from the key, not a scan |
| `winreg.FlushKey(key)` | O(1) | O(1) | Blocks until the key's changes are on disk, however much that is; the registry flushes lazily on its own |
| `winreg.ConnectRegistry(computer_name, key)` | O(1) | O(1) | A handle on another machine's registry; every call through it is a network round trip |

### Values

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winreg.QueryValueEx(key, value_name)` | O(n) | O(n) | Reads into a buffer, then converts it: `str` for `REG_SZ` and `REG_EXPAND_SZ`, `list` for `REG_MULTI_SZ`, `int` for `REG_DWORD` and `REG_QWORD`, `bytes` otherwise; empty data of a `bytes` type comes back as `None` |
| `winreg.QueryValue(key, sub_key)` | O(n) | O(n) | The unnamed default value of `sub_key` as `str`; `''` if it has none |
| `winreg.SetValueEx(key, value_name, reserved, type, value)` | O(n) | O(n) | Converts the Python value to registry data first |
| `winreg.SetValue(key, sub_key, type, value)` | O(n) | O(n) | Sets the default value, creating `sub_key` if needed; `type` must be `REG_SZ` |
| `winreg.DeleteValue(key, value)` | O(1) | O(1) | |
| `winreg.ExpandEnvironmentStrings(str)` | O(s + x) | O(s + x) | Substitutes `%NAME%` from the environment; unknown names are left as written |

### Enumeration

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winreg.EnumKey(key, index)` | O(1) | O(1) | One subkey name; an index past the end raises `OSError` |
| `winreg.EnumValue(key, index)` | O(n) | O(M) | `(name, data, type)` for one value, read into buffers sized for the key's largest value, not this one |
| All subkeys, one `EnumKey()` per index | O(k) | O(1) | k registry calls; `QueryInfoKey()` gives the count up front |
| All values, one `EnumValue()` per index | O(v + V) | O(M) | v registry calls; V = the bytes of every value together. Each call is sized for the largest value |

### Hive files and registry reflection

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winreg.SaveKey(key, file_name)` | O(T) | O(1) | T = the key's whole subtree, written to a hive file; needs the backup privilege |
| `winreg.LoadKey(key, sub_key, file_name)` | O(F) | O(1) | F = the hive file's size, mounted as `sub_key` under `HKEY_USERS` or `HKEY_LOCAL_MACHINE`; needs the restore privilege |
| `winreg.DisableReflectionKey(key)`, `winreg.EnableReflectionKey(key)`, `winreg.QueryReflectionKey(key)` | O(1) | O(1) | 32/64-bit registry reflection; `NotImplementedError` on 32-bit Windows |

### PyHKEY

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `PyHKEY.Close()` | O(1) | O(1) | Also run by the `with` statement and when the object is garbage-collected |
| `PyHKEY.Detach()` | O(1) | O(1) | Returns the integer handle and stops the object from closing it |
| `PyHKEY.handle` | O(1) | O(1) | The integer handle, `0` once closed or detached; `int(key)` is the same and `bool(key)` tests it |
| `winreg.HKEYType` | O(1) | O(1) | The `PyHKEY` class |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `winreg.HKEY_CURRENT_USER`, `winreg.HKEY_LOCAL_MACHINE`, `winreg.HKEY_CLASSES_ROOT`, `winreg.HKEY_USERS`, `winreg.HKEY_CURRENT_CONFIG`, `winreg.HKEY_PERFORMANCE_DATA`, `winreg.HKEY_DYN_DATA` | O(1) | O(1) | Integers naming the predefined root keys, usable wherever a key is |
| `winreg.KEY_*` access rights | O(1) | O(1) | Integer flags for the `access` arguments |
| `winreg.REG_*` value types and options | O(1) | O(1) | Integer flags; the type decides what `QueryValueEx()` converts to |
| `winreg.error` | O(1) | O(1) | Another name for `OSError` |

## Reading and Writing Values

`QueryValueEx()` reads the whole value into a buffer and then converts it, so a read costs the
value's size twice over at its peak. A missing value is `FileNotFoundError`.

```python
import winreg

path = r"Software\winreg-docs-values"
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:  # O(1)
    winreg.SetValueEx(key, "Greeting", 0, winreg.REG_SZ, "hello")  # O(n)
    winreg.SetValueEx(key, "Paths", 0, winreg.REG_MULTI_SZ, ["a", "b"])  # O(n)

    assert winreg.QueryValueEx(key, "Greeting") == ("hello", winreg.REG_SZ)  # O(n)
    assert winreg.QueryValueEx(key, "Paths") == (["a", "b"], winreg.REG_MULTI_SZ)

    try:
        winreg.QueryValueEx(key, "Missing")
    except FileNotFoundError as error:
        assert error.winerror == 2
    else:
        raise AssertionError("a missing value was read")

    winreg.DeleteValue(key, "Paths")  # O(1)
    assert winreg.QueryInfoKey(key)[1] == 1  # O(1) - one value left
winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)  # O(1) - the values go with it
```

### Default Values

Every key has one unnamed value. `QueryValue()` and `SetValue()` reach it through a subkey
name, opening or creating that subkey on the way.

```python
import winreg

path = r"Software\winreg-docs-default"
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
    assert winreg.QueryValue(key, None) == ""  # O(1) - no default value yet

    winreg.SetValue(key, "child", winreg.REG_SZ, "hi")  # O(n) - creates `child`
    assert winreg.QueryValue(key, "child") == "hi"  # O(n)
    assert winreg.QueryInfoKey(key)[0] == 1

    winreg.DeleteKey(key, "child")
winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
```

## Enumerating a Key

Enumeration is by index, one registry call per entry. `QueryInfoKey()` returns both counts
without a scan, so read them once rather than probing until `OSError`.

```python
import winreg

path = r"Software\winreg-docs-enum"
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
    for name in ("a", "b", "c"):
        winreg.CreateKey(key, name).Close()
    winreg.SetValueEx(key, "Size", 0, winreg.REG_DWORD, 42)

    subkey_count, value_count, _ = winreg.QueryInfoKey(key)  # O(1)
    names = [winreg.EnumKey(key, i) for i in range(subkey_count)]  # O(k)
    values = [winreg.EnumValue(key, i) for i in range(value_count)]  # O(v + V) - keeps every value

    assert sorted(names) == ["a", "b", "c"]
    assert values == [("Size", 42, winreg.REG_DWORD)]

    for name in names:
        winreg.DeleteKey(key, name)
winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
```

Indices shift if another process adds or removes entries during the loop. Collect the names
first when you mean to act on them.

### EnumValue Is Sized for the Largest Value

`EnumValue()` asks the key for its largest value and allocates buffers that size on every call,
whichever value it returns. One large value makes every step of a value scan cost that much
memory. To read a value whose name you know, use `QueryValueEx()`, which is sized for that value
alone.

```python
import winreg

path = r"Software\winreg-docs-sizes"
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
    winreg.SetValueEx(key, "Small", 0, winreg.REG_BINARY, b"x")
    winreg.SetValueEx(key, "Large", 0, winreg.REG_BINARY, b"y" * 100_000)

    index = [winreg.EnumValue(key, i)[0] for i in range(2)].index("Small")
    assert winreg.EnumValue(key, index)[1] == b"x"  # O(M) memory - buffers for "Large"
    assert winreg.QueryValueEx(key, "Small")[0] == b"x"  # O(n) - one byte
winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
```

## Deleting a Tree

`DeleteKey()` removes one key and refuses one that still has subkeys, so deleting a tree is a
walk: one call per key, depth first.

```python
import winreg

def delete_tree(parent, name):
    with winreg.OpenKey(parent, name) as key:
        while winreg.QueryInfoKey(key)[0]:  # O(1)
            delete_tree(key, winreg.EnumKey(key, 0))  # O(1) - always the first
    winreg.DeleteKey(parent, name)  # O(1)

path = r"Software\winreg-docs-tree"
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path + r"\a\b"):
    pass

try:
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
except PermissionError as error:
    assert error.winerror == 5
else:
    raise AssertionError("a key with subkeys was deleted")

delete_tree(winreg.HKEY_CURRENT_USER, path)  # O(keys in the tree)
try:
    winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
except FileNotFoundError:
    pass
else:
    raise AssertionError("the tree is still there")
```

## Expanding Environment References

A `REG_EXPAND_SZ` value holds `%NAME%` references, and `QueryValueEx()` returns them as stored.
`ExpandEnvironmentStrings()` substitutes them in one pass over the string.

```python
import os
import winreg

os.environ["WINREG_DOCS_ROOT"] = r"C:\Data"

path = r"Software\winreg-docs-expand"
with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
    winreg.SetValueEx(key, "Logs", 0, winreg.REG_EXPAND_SZ, r"%WINREG_DOCS_ROOT%\logs")
    stored, value_type = winreg.QueryValueEx(key, "Logs")  # O(n) - not expanded
winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)

assert (stored, value_type) == (r"%WINREG_DOCS_ROOT%\logs", winreg.REG_EXPAND_SZ)
assert winreg.ExpandEnvironmentStrings(stored) == r"C:\Data\logs"  # O(s + x)
assert winreg.ExpandEnvironmentStrings("%WINREG_DOCS_UNSET%") == "%WINREG_DOCS_UNSET%"
```

## Handles

A `PyHKEY` closes its handle when the `with` block ends or when it is collected. `Detach()`
hands the integer over to you, and then closing it is your job.

```python
import winreg

key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software")  # O(1)
assert isinstance(key, winreg.HKEYType)
assert key and key.handle == int(key)

raw = key.Detach()  # O(1)
assert not key and key.handle == 0
winreg.CloseKey(raw)  # O(1) - closes the detached integer handle

with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software") as key:
    pass
assert key.handle == 0  # closed by the with statement
```

## Common Patterns

### Reading a Setting With a Fallback

```python
import winreg

def read_setting(path, name, default):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:  # O(1)
            return winreg.QueryValueEx(key, name)[0]  # O(n)
    except FileNotFoundError:
        return default

assert read_setting(r"Software\winreg-docs-absent", "Theme", "light") == "light"
```

## Performance Best Practices

✅ **Do**:

- Take the counts from `QueryInfoKey()` before enumerating instead of probing until `OSError`
- Read a known value with `QueryValueEx()`, which is sized for that value; `EnumValue()` is
  sized for the key's largest
- Open a key once and make several calls through the handle, closing it with `with`
- Keep settings under `HKEY_CURRENT_USER`; writing under `HKEY_LOCAL_MACHINE` needs elevation

❌ **Avoid**:

- `FlushKey()` after every write - it blocks on the disk, and the registry flushes on its own
- Scanning a key with `EnumValue()` when it holds one large value you do not need
- Many small calls through a `ConnectRegistry()` handle, each of which is a network round trip

## Version Notes

- **All Python 3**: Windows only. The bounds above hold on every supported version

## Related Modules

- **[os](os.md)** - `os.environ`, which `ExpandEnvironmentStrings()` reads from
- **[nt](nt.md)** - the other Windows-only low-level module
- **[configparser](configparser.md)** - settings in a file rather than the registry
