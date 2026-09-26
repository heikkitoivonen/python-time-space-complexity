# platform Module Complexity

The `platform` module reports what the interpreter is running on: the operating system, the
machine, the C library and the Python build. Almost every answer is a short string, so what
separates one call from another is not its length but what it has to ask for: a system call, a
file read or a subprocess, and whether the answer is cached for the rest of the process.

The values the operating system reports - `uname` fields, version files, registry and WMI
values - are short and priced O(1). Two inputs can grow: `b` is the bytes of an executable that
`libc_ver()` scans, and `f` is the lines of an os-release file. Each row's Notes say which calls
run a subprocess and which results are cached.

## Complexity Reference

### uname_result

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `platform.uname()` | O(1) | O(1) | On Unix, one `os.uname()` on the first call; every later call returns the same cached `uname_result` |
| `uname_result.system`, `uname_result.node`, `uname_result.release`, `uname_result.version`, `uname_result.machine` | O(1) | O(1) | Fields read from the result; no system call |
| `uname_result.processor` | O(1) | O(1) | On Linux and other Unix, runs `uname -p` in a subprocess on first access, then keeps the answer on that result |
| Iterating, unpacking, indexing or `len()` of a `uname_result` | O(1) | O(1) | Each goes through all six fields, so the first of them resolves `processor` |
| `platform.uname_result` | O(1) | O(1) | The named-tuple class `uname()` returns |

### Cached system queries

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `platform.system()`, `platform.node()`, `platform.release()`, `platform.version()`, `platform.machine()` | O(1) | O(1) | Fields of the cached `uname()` result; none of them needs `processor` |
| `platform.processor()` | O(1) | O(1) | `uname().processor`: on Unix, the `uname -p` subprocess on the first call only |
| `platform.platform(aliased=False, terse=False)` | O(1) | O(1) | Cached per `(aliased, terse)` pair. The first call resolves `processor` and, on Linux, `libc_ver()`; on macOS and other Unix a non-terse first call also runs `architecture()` |
| `platform.freedesktop_os_release()` | O(f) | O(f) | Reads `/etc/os-release` or `/usr/lib/os-release` once, then returns a fresh copy of the cached dictionary on every call; raises `OSError` when neither exists |
| `platform.invalidate_caches()` | O(1) | O(1) | Python 3.14+. Drops the cached `uname()`, `platform()`, os-release and Python build results, so the next call asks again |

### Python build information

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `platform.python_implementation()`, `platform.python_version()`, `platform.python_compiler()`, `platform.python_branch()`, `platform.python_revision()`, `platform.python_build()` | O(1) | O(1) | `sys.version` is parsed once and the fields are cached |
| `platform.python_version_tuple()` | O(1) | O(1) | Three strings, not integers: compare versions with `sys.version_info` instead |

### Uncached probes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `platform.architecture(executable=sys.executable, bits='', linkage='')` | O(1) | O(1) | Not cached: on Unix every call runs `file -b` on the executable in a subprocess |
| `platform.libc_ver()` | O(1) | O(1) | With glibc, one `os.confstr()` call and no file read; without it, scans `sys.executable` as below |
| `platform.libc_ver(executable, lib='', version='', chunksize=16384)` | O(b) | O(chunksize) | b = bytes of the executable, read to the end in `chunksize` pieces on every call |
| `platform.system_alias(system, release, version)` | O(1) | O(1) | Rewrites its arguments (`SunOS` 5.x becomes `Solaris` 2.x); queries nothing |

### Other operating systems

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `platform.mac_ver(release='', versioninfo=('', '', ''), machine='')` | O(1) | O(1) | On macOS, reads and parses `SystemVersion.plist` on every call; elsewhere returns the defaults |
| `platform.win32_ver(release='', version='', csd='', ptype='')` | O(1) | O(1) | On Windows, queries WMI or runs `ver` on every call; elsewhere returns the defaults |
| `platform.win32_edition()`, `platform.win32_is_iot()` | O(1) | O(1) | One registry read on Windows; `None` and `False` elsewhere |
| `platform.ios_ver(system='', release='', model='', is_simulator=False)`, `platform.IOSVersionInfo` | O(1) | O(1) | Python 3.13+. The device's values on iOS, the defaults elsewhere |
| `platform.android_ver(release='', api_level=0, manufacturer='', model='', device='', is_emulator=False)`, `platform.AndroidVer` | O(1) | O(1) | Python 3.13+. System properties read on every call on Android, the defaults elsewhere |
| `platform.java_ver(release='', vendor='', vminfo=('', '', ''), osinfo=('', '', ''))` | O(1) | O(1) | Returns the defaults on anything but Jython; deprecated since Python 3.13 |

## Cached and Uncached Queries

`uname()` and everything derived from it are computed once per process, or until
`invalidate_caches()` on Python 3.14+. `architecture()` and
`libc_ver(executable)` are not: each call repeats the subprocess or the file scan, so call them
once and keep the answer.

```python
import platform

info = platform.uname()               # O(1) - one os.uname() call, then cached
assert platform.uname() is info       # O(1) - the same object every time
assert platform.system() == info.system    # O(1) - a field of the cached result
assert platform.machine() == info.machine  # O(1)

summary = platform.platform()         # O(1) - built on the first call
assert platform.platform() is summary # O(1) - the cached string

bits, linkage = platform.architecture()  # O(1), but a subprocess on every call
assert bits in ('32bit', '64bit')
```

### The processor Field

`processor` is the one `uname()` field that `os.uname()` does not supply. On Linux it comes from
running `uname -p`, so it is resolved only when something asks for it - and iterating,
unpacking or indexing the result asks for it, because those go through all six fields.

```python
import platform

info = platform.uname()               # no subprocess yet
system = info.system                  # O(1) - still none
assert 'processor' not in vars(info)

system, node, release, version, machine, processor = info  # runs uname -p once
assert 'processor' in vars(info)      # kept on the result from now on
assert platform.processor() == processor  # O(1) - the same cached result
```

## Python Version Information

The `python_*()` functions parse `sys.version` once and read a cache afterwards.
`python_version_tuple()` returns strings, which compare as text: `'10' < '9'`, so comparing the
tuple to a version is wrong from Python 3.10 on. `sys.version_info` holds integers.

```python
import platform
import sys

version = platform.python_version()            # O(1) - 'major.minor.patch'
assert version.startswith(f'{sys.version_info.major}.{sys.version_info.minor}.')

major, minor, patch = platform.python_version_tuple()  # O(1) - strings
assert (int(major), int(minor)) == sys.version_info[:2]
assert ('3', '10') < ('3', '9')               # string comparison
assert sys.version_info >= (3, 10)            # integer comparison

assert platform.python_implementation() in ('CPython', 'PyPy', 'Jython')
assert isinstance(platform.python_compiler(), str)
buildno, builddate = platform.python_build()  # O(1)
assert isinstance(builddate, str)
```

## Inspecting a Binary

With no argument and glibc, `libc_ver()` asks glibc for its version and reads no file. Given an
executable, it scans the whole file for libc markers and reports the highest version it finds,
so its cost follows the file's size.

```python
import os
import platform
import tempfile

lib, version = platform.libc_ver()  # O(1) with glibc
assert isinstance(lib, str) and isinstance(version, str)

with tempfile.NamedTemporaryFile(delete=False) as binary:
    binary.write(b'\0' * 50_000 + b'GLIBC_2.17\0' + b'\0' * 50_000 + b'GLIBC_2.28\0')

try:
    assert platform.libc_ver(binary.name) == ('glibc', '2.28')  # O(b)
finally:
    os.remove(binary.name)
```

## Linux Distribution Details

`freedesktop_os_release()` reads the os-release file once. Every later call copies the cached
dictionary, so a caller may change the result without affecting the next one.

```python
import platform

try:
    release = platform.freedesktop_os_release()  # O(f) - read once
except OSError:
    release = None  # os-release information unavailable
else:
    assert {'NAME', 'ID', 'PRETTY_NAME'} <= release.keys()
    release['ID'] = 'changed'
    assert platform.freedesktop_os_release()['ID'] != 'changed'  # a fresh copy
```

## Aliasing System Names

`system_alias()` only rewrites the three strings it is given; it is what `platform(aliased=True)`
applies to the cached `uname()` values.

```python
import platform

assert platform.system_alias('SunOS', '5.8', 'Generic') == ('Solaris', '2.8', 'Generic')
assert platform.system_alias('Linux', '6.1', '#1 SMP') == ('Linux', '6.1', '#1 SMP')
```

## Common Patterns

### Collecting a Diagnostic Report

Every value here comes from a cache after the first call, except `architecture()`, which is
called once and kept.

```python
import platform

def environment_report():
    report = {
        'system': platform.system(),              # O(1) - cached uname()
        'release': platform.release(),           # O(1)
        'machine': platform.machine(),            # O(1)
        'platform': platform.platform(terse=True),  # O(1) after the first call
        'python': platform.python_version(),      # O(1) - cached parse
        'implementation': platform.python_implementation(),
    }
    report['bits'] = platform.architecture()[0]  # a subprocess per call; keep it
    return report

report = environment_report()
assert report['system'] == platform.system()
assert report['bits'] in ('32bit', '64bit')
```

## Performance Best Practices

✅ **Do**:

- Call `system()`, `machine()` and the other `uname()` fields freely: they read one cached result
- Read `uname()` fields by name when you do not need `processor`, so no subprocess runs
- Call `architecture()` once and keep the answer; on Unix it spawns `file` on every call
- Compare Python versions with `sys.version_info`, not `python_version_tuple()`

❌ **Avoid**:

- `architecture()` or `libc_ver(executable)` inside a loop - neither is cached
- Unpacking `uname()` just to read one field - it resolves `processor` with a subprocess

## Version Notes

- **Python 3.13+**: Added `ios_ver()` and `android_ver()`; `java_ver()` is deprecated
- **Python 3.14+**: Added `invalidate_caches()`; `libc_ver()` also recognises musl

## Related Modules

- **[sys](sys.md)** - `sys.platform` and `sys.version_info`, both plain attributes
- **[os](os.md)** - `os.uname()`, the system call behind `platform.uname()`
- **[sysconfig](sysconfig.md)** - build configuration and install paths
- **[subprocess](subprocess.md)** - what `architecture()` and `processor()` run
