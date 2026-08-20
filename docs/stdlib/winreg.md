# winreg Module

The `winreg` module provides access to the Windows registry: opening and
creating keys, reading and writing values, and enumerating subkeys.

It is Windows-only. On other platforms importing it raises
`ModuleNotFoundError`.

## Complexity Reference

### Keys

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OpenKey(key, sub_key)` | O(1) + syscall | O(1) | Returns a handle; use as a context manager |
| `CreateKey(key, sub_key)` | O(1) + syscall | O(1) | Opens if it already exists |
| `CreateKeyEx(key, sub_key, ...)` | O(1) + syscall | O(1) | Explicit access rights and view |
| `CloseKey(hkey)` | O(1) + syscall | O(1) | Release handle |
| `DeleteKey(key, sub_key)` | O(1) + syscall | O(1) | Key must have no subkeys |
| `ConnectRegistry(computer, key)` | O(1) + network | O(1) | Remote registry; latency-bound |
| `QueryInfoKey(key)` | O(1) + syscall | O(1) | Counts of subkeys and values |

### Values

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `QueryValueEx(key, name)` | O(n) + syscall | O(n) | n = value size in bytes |
| `SetValueEx(key, name, 0, type, value)` | O(n) + syscall | O(1) | n = value size |
| `DeleteValue(key, name)` | O(1) + syscall | O(1) | Remove one value |

### Enumeration

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `EnumKey(key, index)` | O(1) + syscall | O(1) | One subkey name by index |
| `EnumValue(key, index)` | O(n) + syscall | O(n) | n = value size; one value by index |
| Full subkey scan | O(k) + k syscalls | O(1) | k = subkey count; one call per index |
| Full value scan | O(v) + v syscalls | O(1) | v = value count |

Enumeration is the operation to watch: each index costs a separate system call,
so walking a key with many subkeys is linear in syscalls, not a single bulk
read.

## Reading a Value

```python
import winreg

# Handles must be closed; the context manager does it - O(1)
with winreg.OpenKey(
    winreg.HKEY_LOCAL_MACHINE,
    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
) as key:
    value, value_type = winreg.QueryValueEx(key, "ProductName")  # O(n)
    print(value)
```

## Enumerating Subkeys

```python
import winreg

with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software") as key:
    # O(1) - read the counts once instead of probing until OSError
    subkey_count, value_count, _ = winreg.QueryInfoKey(key)

    # O(k) with one syscall per iteration
    for index in range(subkey_count):
        print(winreg.EnumKey(key, index))
```

Reading the count up front is both clearer and cheaper than the common pattern
of looping until `EnumKey` raises `OSError`.

!!! warning "Enumeration is not snapshot-consistent"
    Indices shift if another process adds or removes subkeys while you iterate.
    For a stable list, collect the names first and then act on them.

!!! warning "Writes need privileges"
    Writing under `HKEY_LOCAL_MACHINE` generally requires elevation. Prefer
    `HKEY_CURRENT_USER` for per-user settings.

## Version Notes

- **All Python 3 versions**: available on Windows builds only
- **Python 3.11+**: registry handles support the context manager protocol in
  all documented cases, making `CloseKey()` calls unnecessary
- **All versions**: per-call complexity is unchanged; costs are dominated by
  the Windows registry API

## Related Documentation

- [OS Module](os.md)
- [NT Module](nt.md)
- [Platform Module](platform.md)
- [Configparser Module](configparser.md)
