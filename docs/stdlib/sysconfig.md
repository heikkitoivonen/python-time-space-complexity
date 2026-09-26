# sysconfig Module Complexity

The `sysconfig` module reports how this Python was built and where it installs things: the
build's configuration variables, and the install schemes whose path templates, such as
`{base}/bin`, are expanded against them. The configuration variables are loaded on first use and
then cached; install paths are not cached, and every call expands them again from all of
the configuration variables.

`V` is the configuration variables (on POSIX, everything the build recorded from its Makefile
and `pyconfig.h`; far fewer on Windows), `a` is the names passed to `get_config_vars()`, `L` is
the lines in a header file handed to `parse_config_h()`, and `D` is the `#define` and `#undef`
lines among them; header lines are priced as of bounded length. The install-scheme table is a fixed handful of schemes of at most eight paths
each, so scheme and path counts, and the length of one path, are priced as O(1). The first call in
the process to anything that reads configuration variables pays a one-off O(V) load; the bounds
below are for the calls after it. On Python 3.12.8+ and 3.13.1+, a call that finds `sys.prefix`
changed since the load pays it again, into a new dictionary; from 3.14, so does a changed
`sys.exec_prefix`.

## Complexity Reference

### Configuration variables

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sysconfig.get_config_vars()` | O(1) | O(1) | Returns the module's cache itself, not a copy |
| `sysconfig.get_config_vars(*names)` | O(a) | O(a) | A list of values, `None` for an unknown name |
| `sysconfig.get_config_var(name)` | O(1) | O(1) | One dict lookup; `None` for an unknown name |
| `sysconfig.parse_config_h(fp, vars=None)` | O(L) | O(D) | Reads one line at a time and keeps only the definitions; fills and returns `vars` when given |
| `sysconfig.get_makefile_filename()` | O(V) | O(V) | Resolved through `get_path()` in an installed Python |
| `sysconfig.get_config_h_filename()` | O(V) | O(V) | Resolved through `get_path()` in an installed Python |

### Install paths

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sysconfig.get_paths(scheme=get_default_scheme(), vars=None, expand=True)` | O(V) | O(V) | Not cached: every call merges all configuration variables into the substitution dict; a `vars` dict you pass is filled in place |
| `sysconfig.get_paths(scheme, expand=False)` | O(1) | O(1) | The scheme's own template dict, not a copy |
| `sysconfig.get_path(name, scheme=get_default_scheme(), vars=None, expand=True)` | O(V) | O(V) | Expands the whole scheme to return one path |
| `sysconfig.get_path_names()` | O(1) | O(1) | The same tuple on every call |
| `sysconfig.get_scheme_names()` | O(1) | O(1) | A sorted tuple of the fixed scheme table |
| `sysconfig.get_default_scheme()` | O(1) | O(1) | `'venv'` inside a virtual environment, Python 3.11+ |
| `sysconfig.get_preferred_scheme(key)` | O(1) | O(1) | `key` is `'prefix'`, `'home'` or `'user'` |
| `sysconfig._get_preferred_schemes()` | O(1) | O(1) | The hook a redistributor overrides; `get_preferred_scheme()` reads it |

### Platform and build

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sysconfig.get_platform()` | O(1) | O(1) | |
| `sysconfig.get_python_version()` | O(1) | O(1) | The `MAJOR.MINOR` string |
| `sysconfig.is_python_build()` | O(1) | O(1) | At most two file-existence checks |

## Configuration Variables

### Loaded Once, Then Shared

The first call loads every configuration variable into one module-level dictionary, and later
calls hand back that dictionary itself. Reading a variable is a dict lookup, and the dictionary
is the module's own state, not a copy: treat it as read-only.

```python
import sysconfig

config = sysconfig.get_config_vars()  # O(V) on the first call, O(1) after
assert sysconfig.get_config_vars() is config  # the cache itself, not a copy

suffix = sysconfig.get_config_var('EXT_SUFFIX')  # O(1)
assert suffix.endswith(('.so', '.pyd'))
assert sysconfig.get_config_var('NO_SUCH_VARIABLE') is None

version, missing = sysconfig.get_config_vars('py_version_short', 'NO_SUCH_VARIABLE')  # O(a)
assert version == sysconfig.get_python_version()
assert missing is None
```

### Parsing a Header

`parse_config_h()` reads its file a line at a time, so memory follows the definitions it keeps,
not the size of the file.

```python
import io
import sysconfig

header = io.StringIO(
    "/* pyconfig.h */\n"
    "#define HAVE_FORK 1\n"
    "#define PY_NAME \"python\"\n"
    "/* #undef HAVE_NOTHING */\n"
)

values = sysconfig.parse_config_h(header)  # O(L) time, O(D) space
assert values == {'HAVE_FORK': 1, 'PY_NAME': '"python"', 'HAVE_NOTHING': 0}
```

## Install Paths

### Paths Are Expanded on Every Call

`get_paths()` and `get_path()` are not cached. Each call merges every configuration variable into
its substitution dictionary before formatting the scheme's paths, so asking for one path costs
the same O(V) as asking for all of them. Fetch the dictionary once and index it.

```python
import sysconfig

paths = sysconfig.get_paths()  # O(V) - every call expands the whole scheme
assert set(sysconfig.get_path_names()) <= set(paths)

purelib = paths['purelib']  # O(1) - index the dict you already have
assert purelib == sysconfig.get_path('purelib')  # O(V) again, for one path

templates = sysconfig.get_paths(expand=False)  # O(1) - the scheme's own templates
assert '{base}' in templates['purelib']
```

### Overriding Variables

A `vars` dictionary replaces the configuration variables it names. It is also the substitution
dictionary itself: every other configuration variable is copied into it, so pass a copy if you
mean to reuse yours.

```python
import os
import sysconfig

overrides = {'base': '/opt/app'}
paths = sysconfig.get_paths(vars=overrides)  # O(V)
assert paths['purelib'].startswith(os.path.normpath('/opt/app'))

assert overrides['base'] == '/opt/app'  # your value wins...
assert overrides.keys() >= sysconfig.get_config_vars().keys()  # ...and every other one was added
```

### Choosing a Scheme

```python
import sysconfig

names = sysconfig.get_scheme_names()  # O(1) - a fixed table
assert 'posix_prefix' in names and 'nt' in names

assert sysconfig.get_default_scheme() in names  # O(1)
assert sysconfig.get_preferred_scheme('home') in names  # O(1)
assert set(sysconfig._get_preferred_schemes()) == {'prefix', 'home', 'user'}  # O(1)
```

## Platform and Build

```python
import sys
import sysconfig

version = sysconfig.get_python_version()  # O(1)
assert version == f'{sys.version_info[0]}.{sys.version_info[1]}'

platform = sysconfig.get_platform()  # O(1)
if sys.platform == 'win32':
    assert platform.startswith('win')
elif sys.platform == 'linux':
    assert platform.startswith('linux-')

assert isinstance(sysconfig.is_python_build(), bool)  # O(1)
assert sysconfig.get_makefile_filename().endswith('Makefile')  # O(V) - goes through get_path()
assert sysconfig.get_config_h_filename().endswith('pyconfig.h')  # O(V)
```

## Common Patterns

### Locating Install Targets

```python
import os
import sysconfig

paths = sysconfig.get_paths()  # O(V), once
suffix = sysconfig.get_config_var('EXT_SUFFIX')  # O(1)

targets = {
    name: os.path.join(paths['platlib'], name + suffix)  # O(1) per name
    for name in ('_speedups', '_parser')
}
assert all(target.startswith(paths['platlib']) for target in targets.values())
```

## Performance Best Practices

✅ **Do**:

- Call `get_paths()` once and index the result: each `get_path()` call costs as much as the whole dict
- Read `get_config_var()` freely; after the first call it is a dict lookup
- Pass a copy as `vars` when you need your dictionary unchanged

❌ **Avoid**:

- `get_path()`, `get_makefile_filename()` or `get_config_h_filename()` in a loop - each call is O(V)
- Mutating what `get_config_vars()` or `get_paths(expand=False)` returns: it is the module's own
  state, not a copy

## Version Notes

- **Python 3.11+**: `get_default_scheme()` and `get_preferred_scheme('prefix')` return `'venv'` inside a virtual environment
- **Python 3.11+**: `get_config_var('SO')` returns `None`; use `'EXT_SUFFIX'`

## Related Modules

- **[sys](sys.md)** - `sys.prefix` and `sys.base_prefix`, which the install paths expand from
- **[site](site.md)** - adds the site-packages directories these schemes name to `sys.path`
- **[venv](venv.md)** - creates the environments the `venv` scheme describes
- **[platform](platform.md)** - richer platform identification than `get_platform()`
