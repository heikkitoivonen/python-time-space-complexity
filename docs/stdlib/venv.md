# venv Module Complexity

The `venv` module creates virtual environments: a directory holding a `pyvenv.cfg`, the
interpreter under a few names, and activation scripts. The standard library is not copied: the
environment's interpreter uses the base installation's. Creation is filesystem work, and with
pip it also runs a subprocess.

`b` is the size of the interpreter executable when the environment copies it, which is what
`venv.create()` and `EnvBuilder` do by default; with `symlinks=True`, and from `python -m venv`
on POSIX, each name is a link and `b` is O(1). `e` is the entries, at any depth, already under
the target directory, `t` is the bytes of activation-script templates installed, and `p` is the
files pip installs. Path lengths and venv's own fixed set of directories and scripts count as
O(1). Space is what the call writes to disk.

## Complexity Reference

### create

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `venv.create(env_dir, system_site_packages=False, clear=False, symlinks=False, with_pip=False, prompt=None, upgrade_deps=False, *, scm_ignore_files=frozenset())` | O(b) | O(b) | Builds an `EnvBuilder` from the options and calls its `create()`; the options below cost the same here |

### EnvBuilder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `venv.EnvBuilder(system_site_packages=False, clear=False, symlinks=False, upgrade=False, with_pip=False, prompt=None, upgrade_deps=False, *, scm_ignore_files=frozenset())` | O(1) | O(1) | Stores the options; touches no files |
| `EnvBuilder.create(env_dir)` | O(b) | O(b) | Directories, `pyvenv.cfg`, the interpreter under each of its names, and the activation scripts |
| `EnvBuilder(clear=True).create(env_dir)` | O(e + b) | O(b) | Deletes every entry already in `env_dir` first, including files venv did not create |
| `EnvBuilder(system_site_packages=True).create(env_dir)` | O(b) | O(b) | One line in `pyvenv.cfg`; nothing is copied from the system site-packages |
| `EnvBuilder(with_pip=True).create(env_dir)` | O(b + p) | O(b + p) | Adds one subprocess running `ensurepip` in the new environment; it installs the bundled pip, with no network |
| `EnvBuilder(upgrade_deps=True).create(env_dir)` | O(b + p) + network | O(b + p) | Adds one subprocess running `pip install --upgrade`, which queries the package index; fails if the environment cannot import pip |
| `EnvBuilder(upgrade=True).create(env_dir)` | O(b) | O(b) | Rewrites `pyvenv.cfg` and calls `setup_python()` again on an existing environment; installs no scripts, skips `post_setup()`, and leaves installed packages in place |
| `EnvBuilder(scm_ignore_files={'git'}).create(env_dir)` | O(b) | O(b) | Python 3.13+; adds a `.gitignore` that ignores the whole environment |

### Customisation hooks

`create()` calls these, passing each the context object `ensure_directories()` returns. Override
one in a subclass to change that step.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `EnvBuilder.ensure_directories(env_dir)` | O(1) | O(1) | Creates the directory tree and returns the context; O(e) with `clear=True` |
| `EnvBuilder.create_git_ignore_file(context)` | O(1) | O(1) | Python 3.13+; called when `scm_ignore_files` contains `'git'` |
| `EnvBuilder.create_configuration(context)` | O(1) | O(1) | Writes `pyvenv.cfg` |
| `EnvBuilder.setup_python(context)` | O(b) | O(b) | Copies or links the interpreter under each of its names |
| `EnvBuilder.setup_scripts(context)` | O(1) | O(1) | Calls `install_scripts()` on venv's own templates, a fixed set of small files |
| `EnvBuilder.install_scripts(context, path)` | O(t) | O(t) | t = bytes of the templates under `path`'s `common` and `os.name` subdirectories; placeholders such as `__VENV_DIR__` are replaced in each |
| `EnvBuilder.post_setup(context)` | O(1) | O(1) | Does nothing; an override costs what it does |
| `EnvBuilder.upgrade_dependencies(context)` | O(p) + network | O(p) | Runs `pip install --upgrade pip` in the environment, `pip setuptools` before Python 3.12 |

## Creating an Environment

### Copies vs Symlinks

`venv.create()` and `EnvBuilder` copy the interpreter executable under every name the
environment gives it, so creating one writes a few times the executable's size. `symlinks=True`
makes each name a link instead, which is also what `python -m venv` does on POSIX.

```python
import os
import tempfile
import venv

with tempfile.TemporaryDirectory() as tmp:
    copied = os.path.join(tmp, 'copied')
    builder = venv.EnvBuilder()
    builder.create(copied)  # O(b) - one copy per name
    context = builder.ensure_directories(copied)  # O(1) - the tree already exists
    executable = os.path.realpath(context.executable)
    for name in ('python', 'python3'):
        path = os.path.join(context.bin_path, name)
        assert not os.path.islink(path)
        assert os.path.getsize(path) == os.path.getsize(executable)

    linked = os.path.join(tmp, 'linked')
    venv.create(linked, symlinks=True)  # O(1) - links only
    for name in ('python', 'python3'):
        path = os.path.join(linked, 'bin', name)
        assert os.path.islink(path)
        assert os.path.realpath(path) == executable
```

The block uses the POSIX layout; on Windows the directory is `Scripts` and the copied file is a
launcher, not the interpreter.

### What Goes Into It

Nothing from the standard library or the base installation's site-packages is copied. The
environment is a fixed handful of files whatever the size of the installation it points at.

```python
import os
import tempfile
import venv

with tempfile.TemporaryDirectory() as tmp:
    env = os.path.join(tmp, 'env')
    builder = venv.EnvBuilder(symlinks=True, system_site_packages=True)
    builder.create(env)

    files = [
        os.path.relpath(os.path.join(root, name), env)
        for root, _, names in os.walk(env)
        for name in names
    ]
    assert len(files) < 20
    assert not any(name.endswith('.py') for name in files)

    with open(os.path.join(env, 'pyvenv.cfg'), encoding='utf-8') as cfg:
        config = cfg.read()
    home = builder.ensure_directories(env).python_dir
    assert f'home = {home}\n' in config
    assert 'include-system-site-packages = true\n' in config
```

## Using an Environment Without Activating

Activation is a shell script the module installs, which puts the environment's `bin` first on
`PATH` for that shell. Code does not need it: running the environment's interpreter by its path
is enough for that interpreter to use the environment.

```python
import os
import subprocess
import sys
import tempfile
import venv

with tempfile.TemporaryDirectory() as tmp:
    env = os.path.join(tmp, 'env')
    builder = venv.EnvBuilder(symlinks=True)
    builder.create(env)  # O(1) with symlinks
    context = builder.ensure_directories(env)  # O(1) - the tree already exists

    output = subprocess.run(
        [context.env_exe, '-c', 'import sys; print(sys.prefix); print(sys.base_prefix)'],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    assert os.path.realpath(output[0]) == os.path.realpath(env)
    assert output[1] == sys.base_prefix
```

## Recreating an Environment

`clear=True` deletes everything already in the directory before building, so its cost follows
what was there. It does not check that the directory was an environment: point it at the wrong
directory and that directory is emptied.

```python
import os
import tempfile
import venv

with tempfile.TemporaryDirectory() as tmp:
    env = os.path.join(tmp, 'env')
    os.makedirs(env)
    with open(os.path.join(env, 'notes.txt'), 'w') as f:
        f.write('not part of any environment')

    venv.create(env, symlinks=True, clear=True)  # O(e) to empty it first
    assert not os.path.exists(os.path.join(env, 'notes.txt'))
    assert os.path.exists(os.path.join(env, 'pyvenv.cfg'))
```

## Installing pip

`with_pip=True` starts the environment's interpreter once to run `ensurepip`, which installs the
pip wheel bundled with Python. Nothing is downloaded, but pip's files outnumber the rest of the
environment many times over. `upgrade_deps=True` starts it again to run `pip install --upgrade`,
which queries the package index. Leave both off when the environment only needs to exist, such
as in a test that runs its interpreter.

## Common Patterns

### Adding Files in post_setup

A subclass can extend any step. `post_setup()` runs once the interpreter and the scripts are in
place, and receives the same context as every other hook.

```python
import os
import tempfile
import venv

class WithMarker(venv.EnvBuilder):
    def post_setup(self, context):
        path = os.path.join(context.env_dir, 'marker.txt')
        with open(path, 'w', encoding='utf-8') as f:  # O(1)
            f.write(context.env_name)

with tempfile.TemporaryDirectory() as tmp:
    env = os.path.join(tmp, 'project')
    WithMarker(symlinks=True).create(env)
    with open(os.path.join(env, 'marker.txt'), encoding='utf-8') as f:
        assert f.read() == 'project'
```

## Performance Best Practices

✅ **Do**:

- Pass `symlinks=True` to `venv.create()` or `EnvBuilder` on POSIX; the default copies the
  interpreter under every name
- Run the environment's interpreter by path instead of activating it from code
- Leave `with_pip` off when nothing will be installed; pip's files outnumber the rest of the
  environment many times over

❌ **Avoid**:

- `clear=True` on a directory you have not checked - it deletes everything in it
- `upgrade_deps=True` where the network is unavailable or slow; it queries the package index

## Version Notes

- **Python 3.12+**: `with_pip` and `upgrade_deps` install or upgrade only pip, not setuptools
- **Python 3.13+**: Added `scm_ignore_files` and `create_git_ignore_file()`; `python -m venv`
  writes a `.gitignore` unless given `--without-scm-ignore-files`, while `venv.create()` and
  `EnvBuilder` write none by default
- **All Python 3**: `venv.create()` and `EnvBuilder` copy the interpreter by default; `python -m
  venv` links it on POSIX and copies it on Windows

## Related Modules

- **[ensurepip](ensurepip.md)** - what `with_pip=True` runs, and what it installs
- **[site](site.md)** - reads `pyvenv.cfg` when the environment's interpreter starts
- **[sysconfig](sysconfig.md)** - the `venv` install scheme that lays out the environment
- **[subprocess](subprocess.md)** - running the environment's interpreter without activating it
