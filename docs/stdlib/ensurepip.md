# ensurepip Module Complexity

The `ensurepip` module installs the pip that ships inside Python, without a network. It does no
installing itself: `bootstrap()` copies the bundled wheels to a temporary directory and runs pip
from them in one child interpreter, which unpacks and installs them.

`p` is the size of the bundled wheels: pip's, plus setuptools' on Python 3.10 and 3.11. It is
fixed by the Python release, so no argument changes it. Space is what the call writes to disk.
The bounds are for the wheels Python bundles; a build configured with `--with-wheel-pkg-dir`
installs a pip wheel from that directory instead.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ensurepip.version()` | O(1) | O(1) | The bundled pip's version string; nothing is run or installed |
| `ensurepip.bootstrap(*, root=None, upgrade=False, user=False, altinstall=False, default_pip=False, verbosity=0)` | O(p) | O(p) | One child interpreter runs pip with `--no-index`, so nothing is downloaded; returns `None` and raises `subprocess.CalledProcessError` if pip fails |
| `bootstrap(upgrade=True)` | O(p) | O(p) | Without it, a pip the running interpreter already has, of any version, satisfies the request, even with `root`, and no pip is installed |
| `bootstrap(root=..., user=True, verbosity=...)` | O(p) | O(p) | Change where pip installs and how much it prints, not the cost |
| `bootstrap(altinstall=True)`, `bootstrap(default_pip=True)` | O(p) | O(p) | Choose the scripts: `pipX` and `pipX.Y` by default, only `pipX.Y` with `altinstall`, plus `pip` with `default_pip`; both together raise `ValueError` before anything runs |

### Command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m ensurepip [--upgrade] [--user] [--root DIR] [--altinstall] [--default-pip] [-v]` | O(p) | O(p) | The same `bootstrap()`, with the same options |
| `python -m ensurepip --version` | O(1) | O(1) | Prints the bundled pip's version and installs nothing |

## Bootstrapping pip

### Installing the Bundled Wheel

`bootstrap()` costs a pip install of the bundled wheel whatever the arguments, so it belongs in
setup, not in a loop. Without `upgrade=True` it installs pip only when the interpreter calling it
has none yet, so this example calls it from a new environment built without one.

```python
import ensurepip
import os
import subprocess
import tempfile
import venv

with tempfile.TemporaryDirectory() as env:
    builder = venv.EnvBuilder(symlinks=os.name != 'nt')  # link the interpreter where it can
    builder.create(env)  # no pip yet
    context = builder.ensure_directories(env)

    install = 'import ensurepip; ensurepip.bootstrap()'
    subprocess.run([context.env_exe, '-c', install], check=True, capture_output=True)  # O(p)

    scripts = {name.removesuffix('.exe') for name in os.listdir(context.bin_path)}
    assert 'pip3' in scripts      # pipX, beside pipX.Y
    assert 'pip' not in scripts   # only default_pip=True adds the unqualified name

# altinstall and default_pip contradict each other, and nothing runs
try:
    ensurepip.bootstrap(altinstall=True, default_pip=True)
except ValueError as error:
    assert 'altinstall' in str(error)
else:
    raise AssertionError('altinstall and default_pip were accepted together')
```

### Checking the Bundled Version

`version()` installs nothing. Asking it, or `python -m ensurepip --version`, is how to learn what
`bootstrap()` would install without installing it.

```python
import ensurepip
import subprocess
import sys

bundled = ensurepip.version()  # O(1)
assert bundled.split('.')[0].isdigit()

result = subprocess.run(
    [sys.executable, '-m', 'ensurepip', '--version'],
    capture_output=True, text=True, check=True,
)  # one interpreter start-up; installs nothing
assert result.stdout.strip() == f'pip {bundled}'
```

### Side Effects on os.environ

`bootstrap()` deletes every `PIP_*` variable from `os.environ` and points `PIP_CONFIG_FILE` at
the null device, so that user settings cannot reach the install. The change outlives the call,
and every child process started afterwards inherits it. It also sets `ENSUREPIP_OPTIONS` to pick
the scripts, and `default_pip=True` does not reset it: after a call without `default_pip` in the
same process, a call with it installs no `pip`. Run `python -m ensurepip` as a subprocess where
the calling process still needs its pip settings or will bootstrap again.

## Performance Best Practices

✅ **Do**:

- Check `ensurepip.version()` before installing when you only need to know the version
- Pass `upgrade=True` when an older installed pip should be replaced; without it nothing is
  reinstalled
- Use `python -m venv`, which runs `ensurepip` for you, when the goal is a fresh environment

❌ **Avoid**:

- Calling `bootstrap()` to make sure pip is present on every run - even when pip is there, each
  call copies the wheels and starts pip in a new interpreter
- Expecting `bootstrap()` to fetch a newer pip; it installs only the bundled wheel

## Version Notes

- **Python 3.12+**: `bootstrap()` installs pip only; on 3.10 and 3.11 it also installs the bundled
  setuptools
- **All Python 3**: The bundled pip changes between patch releases, so read `version()` rather
  than assuming one; some Linux distributions remove `ensurepip` or point it at their own wheels

## Related Modules

- **[venv](venv.md)** - `with_pip=True` runs `python -m ensurepip` in the new environment
- **[subprocess](subprocess.md)** - the child interpreter `bootstrap()` starts, and the
  `CalledProcessError` it raises
