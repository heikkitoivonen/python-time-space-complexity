# distutils Module Complexity

The `distutils` package builds and installs Python packages. A setup script calls `setup()`,
which parses options and runs commands; the commands compile C sources through a `CCompiler`,
copy files into build and install trees, and create archives. Nearly all of the time goes to
copying bytes and to external programs such as the C compiler. The Python side makes a few
filesystem calls per file, and uses modification times to decide which files it can skip.

!!! warning "Removed in Python 3.12"
    Deprecated in Python 3.10 by PEP 632 and removed in Python 3.12. The examples need
    Python 3.10 or 3.11.

`n` is the items in the list or directory tree an operation is given (sources, objects, library
names, files), `b` is the bytes those files hold, `d` is the components of a path, `L` is the
characters of a string argument, `w` is the words in it, and `s` is the directories searched.
A filesystem metadata call (`stat`, `mkdir`, `rename`, `unlink`) and building a path from its
parts are priced at O(1) unless a row's bound is in `L`. Running an external program counts as
one step: the compiler's, linker's or archiver's own work is not priced here.

## Complexity Reference

### setup and Distribution

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.core.setup(**attrs)` | O(c) command runs | O(c) | c = commands named on the command line. Reads the config files, parses the command line, then runs each command once: a command named twice runs once |
| `distutils.core.run_setup(script_name, script_args=None, stop_after="run")` | As `setup()` | O(c) | Runs the script with `exec()`; `stop_after` of `"init"`, `"config"` or `"commandline"` returns the `Distribution` before any command runs |
| `distutils.core.Distribution(attrs=None)` | O(e) | O(e) | e = the size of `attrs`, counting what is nested in it: `options` entries and the `keywords` and `platforms` strings it splits. The class lives in `distutils.dist` |
| `Distribution.run_command(command)` | O(1) + the command | O(1) | Skips a command that has already run; `reinitialize_command()` makes it runnable again |
| `distutils.core.Extension(name, sources, ...)` | O(n) | O(1) | Checks that every source is a `str`, then keeps the `sources` list it is given, not a copy. Defined in `distutils.extension` |

### Command

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.core.Command(dist)` | O(1) + `initialize_options()` | O(1) | The same class as `distutils.cmd.Command`. Constructing the base class itself raises `RuntimeError` |
| `Command.initialize_options()`, `Command.finalize_options()`, `Command.run()` | The subclass's | The subclass's | Abstract: the base versions raise `RuntimeError` |
| `Command.sub_commands` | O(1) | O(1) | A class-level list of `(name, predicate)` pairs; `get_sub_commands()` calls every predicate |

### Commands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.command.build` | Its sub-commands' | O(1) | Runs `build_py`, `build_clib`, `build_ext` and `build_scripts`, each only when the distribution has something for it |
| `distutils.command.build_py`, `distutils.command.build_scripts`, `distutils.command.install_lib`, `distutils.command.install_headers`, `distutils.command.install_scripts`, `distutils.command.install_data` | O(n·d + b) | O(n) + one file | Copy files. A file whose copy is at least as new as the source is skipped unless `--force` is given. d is the depth of a copied tree, as in `copy_tree()` |
| `distutils.command.build_py.build_py_2to3` | O(n + b) + 2to3 | O(n) + one file | As `build_py`, then runs `lib2to3` over the modules this run copied |
| `distutils.command.build_ext` | O(n) compiler runs per extension | O(n) | An extension whose output is newer than all of its sources and `depends` is skipped; otherwise, or with `--force`, every one of its sources is compiled again, then linked |
| `distutils.command.build_clib` | O(n) compiler runs per library | O(n) | Compiles every source on every run; only the archiver run is skipped when the library is up to date and `--force` is not given |
| `distutils.command.install` | O(n·d + b) | O(n) + one file | Runs `build` (unless `--skip-build`) and then the `install_*` commands |
| `distutils.command.clean` | O(n) | O(n) | Removes the temporary build tree; `--all` removes the other build directories too |
| `distutils.command.sdist` | O(t·n·(r + log(t·n)) + b) | O(t·n) | t = patterns in `MANIFEST.in` plus one for the default files, r = entries removed, by an exclusion or as duplicates of an earlier match. Each pattern is matched against all n files of the tree, and the list keeps one entry per match until it is sorted and deduplicated; each removal deletes from that list. The files are then linked or copied into a release tree and archived |
| `distutils.command.bdist`, `distutils.command.bdist_dumb` | O(n·d + n log n + b) | O(n) | Install into a temporary tree, then archive it with `make_archive()` |
| `distutils.command.bdist_rpm` | As `sdist`, plus `rpmbuild` | O(n) | Runs `sdist`, writes a spec file and runs `rpmbuild` on them |
| `distutils.command.bdist_msi` | O(n + b) | O(n) | Python 3.10 on Windows only: it needs `msilib` |
| `distutils.command.bdist_packager` | - | - | Named in the 3.10 and 3.11 documentation index, but no such module ships |
| `distutils.command.check` | O(1) | O(1) | Warns about missing required metadata. `--restructuredtext` also parses the long description, which needs a parser outside the standard library |
| `distutils.command.config` | O(1) compiler runs per `try_*` call | O(1) | Each call writes a test program: `try_compile()` compiles it, `try_link()` also links it, and `try_run()` also runs it |
| `distutils.command.register` | Network round trips | O(L) | L = the metadata sent and the responses read; talks to the package index |

### CCompiler

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.ccompiler.new_compiler(plat=None, compiler=None, verbose=0, dry_run=0, force=0)` | O(1) | O(1) | Imports the compiler's module on first use. The executables are the class defaults (`cc` on Unix) until `customize_compiler()` |
| `distutils.ccompiler.get_default_compiler(osname=None, platform=None)` | O(1) | O(1) | `'unix'` on POSIX, `'msvc'` on Windows |
| `distutils.ccompiler.show_compilers()` | O(1) | O(1) | Prints the fixed table of compiler names |
| `distutils.ccompiler.gen_preprocess_options(macros, include_dirs)` | O(m + s) | O(m + s) | m = macros |
| `distutils.ccompiler.gen_lib_options(compiler, library_dirs, runtime_library_dirs, libraries)` | O(n + s) | O(n + s) | A library name with a directory part is looked up with `find_library_file()` |
| `CCompiler.define_macro(name, value=None)`, `CCompiler.undefine_macro(name)` | O(m) | O(1) | m = macros already set; an earlier entry for the name is replaced |
| `CCompiler.add_include_dir(dir)`, `CCompiler.add_library(libname)`, `CCompiler.add_library_dir(dir)`, `CCompiler.add_runtime_library_dir(dir)`, `CCompiler.add_link_object(object)` | O(1) | O(1) | Append to the compiler's list |
| `CCompiler.set_include_dirs(dirs)`, `CCompiler.set_libraries(libnames)`, `CCompiler.set_library_dirs(dirs)`, `CCompiler.set_runtime_library_dirs(dirs)`, `CCompiler.set_link_objects(objects)` | O(n) | O(n) | Store a copy: later changes to the caller's list do not reach the compiler |
| `CCompiler.set_executables(**kwargs)` | O(L·w) | O(L) | Splits each command string with `split_quoted()` |
| `CCompiler.compile(sources, output_dir=None, macros=None, include_dirs=None, debug=0, extra_preargs=None, extra_postargs=None, depends=None)` | O(n) compiler runs | O(n + m + s) | `UnixCCompiler` runs once per source on every call; neither timestamps nor `depends` make it skip one |
| `CCompiler.preprocess(source, output_file=None, macros=None, include_dirs=None, extra_preargs=None, extra_postargs=None)` | One preprocessor run | O(m + s) | `UnixCCompiler` skips it when `output_file` is newer than `source`, unless the compiler was made with `force=1` |
| `CCompiler.create_static_lib(objects, output_libname, output_dir=None, debug=0, target_lang=None)` | O(n) | O(n) | One archiver run (plus `ranlib` on macOS), skipped when the library is newer than every object unless the compiler was made with `force=1` |
| `CCompiler.link(target_desc, objects, output_filename, ...)`, `CCompiler.link_shared_lib(...)`, `CCompiler.link_shared_object(...)`, `CCompiler.link_executable(...)` | O(n + s) | O(n + s) | One linker run, skipped when the output is newer than every object unless the compiler was made with `force=1` |
| `CCompiler.has_function(funcname, includes=None, include_dirs=None, libraries=None, library_dirs=None)` | At most two compiler runs | O(n + s) | Writes a test program, compiles it, then links it |
| `CCompiler.find_library_file(dirs, lib, debug=0)` | O(s) | O(1) | Stops at the first directory that holds the library |
| `CCompiler.library_dir_option(dir)`, `CCompiler.runtime_library_dir_option(dir)`, `CCompiler.library_option(lib)` | O(1) | O(1) | One command-line option |
| `CCompiler.object_filenames(source_filenames, strip_dir=0, output_dir='')` | O(n) | O(n) | String work only; an unknown extension raises `UnknownFileError` |
| `CCompiler.shared_object_filename(basename, ...)`, `CCompiler.library_filename(libname, ...)`, `CCompiler.executable_filename(basename, ...)` | O(1) | O(1) | String work only |
| `CCompiler.detect_language(sources)` | O(n) | O(1) | |
| `CCompiler.announce(msg, level=1)`, `CCompiler.debug_print(msg)`, `CCompiler.warn(msg)` | O(L) | O(L) | `debug_print()` prints only when `DISTUTILS_DEBUG` is set |
| `CCompiler.execute(func, args, msg=None, level=1)`, `CCompiler.spawn(cmd)`, `CCompiler.move_file(src, dst)`, `CCompiler.mkpath(name, mode=0o777)` | As `util.execute()`, `spawn.spawn()`, `file_util.move_file()`, `dir_util.mkpath()` | Same | `spawn()`, `move_file()` and `mkpath()` pass the compiler's `dry_run` on; `execute()` does not, and always calls `func` |
| `distutils.unixccompiler`, `distutils.cygwinccompiler`, `distutils.msvccompiler`, `distutils.bcppcompiler` | As `CCompiler` | As `CCompiler` | Concrete compiler classes; `UnixCCompiler` is the one used on Linux and macOS |

### Files and Directories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.dep_util.newer(source, target)` | O(1) | O(1) | True when `target` is missing. Compares whole-second modification times, so a change within the same second as the target is not seen |
| `distutils.dep_util.newer_pairwise(sources, targets)` | O(n) | O(n) | |
| `distutils.dep_util.newer_group(sources, target, missing='error')` | O(n) | O(1) | Stops at the first source newer than `target` |
| `distutils.file_util.copy_file(src, dst, preserve_mode=1, preserve_times=1, update=0, link=None, verbose=1, dry_run=0)` | O(b) | O(1) | With `update=1`, O(1) when `dst` is not older. `link='hard'` or `'sym'` is O(1) when the link is made; a failed hard link falls back to copying |
| `distutils.file_util.move_file(src, dst, verbose=1, dry_run=0)` | O(1); O(b) across filesystems | O(1) | A rename, falling back to copy and delete |
| `distutils.file_util.write_file(filename, contents)` | O(L) | O(longest string) | Writes each string followed by a newline |
| `distutils.dir_util.mkpath(name, mode=0o777, verbose=1, dry_run=0)` | O(d) | O(d) | Returns the directories it created. Remembers them for the life of the process and skips them later, even if they were deleted meanwhile by anything but `remove_tree()` |
| `distutils.dir_util.create_tree(base_dir, files, mode=0o777, verbose=1, dry_run=0)` | O(n log n + n·d) | O(n·d) | One `mkpath()` per distinct directory |
| `distutils.dir_util.copy_tree(src, dst, preserve_mode=1, preserve_times=1, preserve_symlinks=0, update=0, verbose=1, dry_run=0)` | O(n·d + b) | O(n) | d = depth of the tree: each name is also copied into the result list of every directory above it. Returns the destination names, including files `update=1` skipped; names starting with `.nfs` are ignored |
| `distutils.dir_util.remove_tree(directory, verbose=1, dry_run=0)` | O(n) | O(n) | Lists the whole tree before deleting anything; a failed deletion is logged, not raised |
| `distutils.archive_util.make_tarball(base_name, base_dir, compress="gzip", verbose=0, dry_run=0, owner=None, group=None)` | O(n log n + b) | O(n) | `compress` is `"gzip"`, `"bzip2"`, `"xz"` or `None`; `"compress"` runs the external `compress` program |
| `distutils.archive_util.make_zipfile(base_name, base_dir, verbose=0, dry_run=0)` | O(n + b) | O(n) | |
| `distutils.archive_util.make_archive(base_name, format, root_dir=None, base_dir=None, verbose=0, dry_run=0, owner=None, group=None)` | O(n log n + b) | O(n) | As the format's function: tar formats sort each directory's entries. Changes the process's working directory to `root_dir` while it runs |

### distutils.util

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.util.get_platform()` | O(1) | O(1) | |
| `distutils.util.convert_path(pathname)` | O(1) on POSIX; O(L) on Windows | O(1); O(L) | On POSIX the argument itself is returned |
| `distutils.util.change_root(new_root, pathname)` | O(L) | O(L) | |
| `distutils.util.check_environ()` | O(1) | O(1) | Fills in `HOME` and `PLAT` in `os.environ` where they are missing, the first time; later calls return at once |
| `distutils.util.subst_vars(s, local_vars)` | O(L) | O(L) | L counts the result as well as `s`. `$name` from `local_vars`, then `os.environ`; an unknown name raises `ValueError` |
| `distutils.util.split_quoted(s)` | O(L·w) | O(L) | Shell-like words, quotes and backslash escapes |
| `distutils.util.execute(func, args, msg=None, verbose=0, dry_run=0)` | O(1) + `func` | O(1) | With `dry_run`, logs without calling `func` |
| `distutils.util.strtobool(val)` | O(L) | O(L) | |
| `distutils.util.byte_compile(py_files, optimize=0, force=0, prefix=None, base_dir=None, verbose=1, dry_run=0, direct=None)` | O(n + b) | O(n) + one file | Skips a `.pyc` that is up to date unless `force`. With `direct` left as `None` and `optimize` set, or under `-O`, writes a script naming the files and runs it in a new interpreter |
| `distutils.util.rfc822_escape(header)` | O(L) | O(L) | |

### TextFile and FancyGetopt

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.text_file.TextFile(filename=None, file=None, **options)` | O(1) | O(1) | Opens `filename` unless `file` is given |
| `TextFile.open(filename)`, `TextFile.close()` | O(1) | O(1) | |
| `TextFile.readline()` | O(L); O(L·p) when joining | O(L) | L = characters of the physical lines read, including skipped blank and comment lines; p = physical lines joined by `join_lines`. Returns `None` at the end |
| `TextFile.readlines()` | Its `readline()` calls | O(L) | The rest of the file |
| `TextFile.unreadline(line)` | O(1) | O(1) | The next `readline()` returns the most recently pushed line |
| `TextFile.warn(msg, line=None)` | O(L) | O(L) | Writes to `sys.stderr` |
| `distutils.fancy_getopt.FancyGetopt(option_table=None)` | O(o) | O(o) | o = options in the table |
| `FancyGetopt.getopt(args=None, object=None)` | O(o + a·o + a²) | O(o + a) | a = arguments; each long option is matched against all o, and `getopt` copies the remaining arguments after each one |
| `FancyGetopt.get_option_order()` | O(1) | O(1) | The parser's own list, which keeps growing across `getopt()` calls |
| `FancyGetopt.generate_help(header=None)` | O(o) `wrap_text()` calls | O(o + L) | One per option's help string |
| `distutils.fancy_getopt.fancy_getopt(options, negative_opt, object, args)` | O(o + a·o + a²) | O(o + a) | Builds a parser and calls `getopt()` |
| `distutils.fancy_getopt.wrap_text(text, width)` | O(L + w²) | O(L) | |

### Versions, Logging and Configuration

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `distutils.version.StrictVersion(vstring=None)`, `distutils.version.LooseVersion(vstring=None)` | O(L) | O(L) | |
| Comparing versions (`<`, `==`, ...) | O(L) | O(1); O(L) for a `str` operand | A `str` operand is parsed again on every comparison. `LooseVersion` raises `TypeError` when the first components that differ are a number in one version and letters in the other |
| `distutils.log.debug(msg, *args)`, `info`, `warn`, `error`, `fatal`, `log(level, msg, *args)` | O(L) emitted; O(1) below the threshold | O(L) | `msg % args` is formatted only when the level reaches the threshold. Not the `logging` module |
| `distutils.log.set_threshold(level)`, `distutils.log.set_verbosity(v)` | O(1) | O(1) | |
| `distutils.spawn.spawn(cmd, search_path=1, verbose=0, dry_run=0)` | O(s) + the program | O(n + s) | Searches `PATH` for `cmd[0]`, then waits for the program; a non-zero exit raises `DistutilsExecError` |
| `distutils.spawn.find_executable(executable, path=None)` | O(s) | O(s) | The first match, or `None` |
| `distutils.sysconfig.get_config_var(name)`, `distutils.sysconfig.get_config_vars(*args)`, `distutils.sysconfig.get_config_h_filename()`, `distutils.sysconfig.get_makefile_filename()` | O(1); O(n) for n names | O(1); O(n) | The `sysconfig` functions themselves |
| `distutils.sysconfig.PREFIX`, `distutils.sysconfig.EXEC_PREFIX` | O(1) | O(1) | |
| `distutils.sysconfig.get_python_inc(plat_specific=0, prefix=None)`, `distutils.sysconfig.get_python_lib(plat_specific=0, standard_lib=0, prefix=None)` | O(1) | O(1) | Built from the prefix; nothing is checked on disk |
| `distutils.sysconfig.customize_compiler(compiler)` | O(L·w) | O(L) | Sets a Unix compiler's executables from Python's build configuration and the `CC`, `CFLAGS`, `LDFLAGS` and related environment variables |
| `distutils.sysconfig.set_python_build()` | - | - | Documented, but not defined by the module |
| `distutils.filelist.FileList.findall(dir=os.curdir)` | O(n) | O(n) | Walks the tree, following symbolic links |
| `FileList.include_pattern(pattern, anchor=1, prefix=None, is_regex=0)` | O(n) | O(n) | Matches the pattern against every file of the tree |
| `FileList.exclude_pattern(pattern, anchor=1, prefix=None, is_regex=0)` | O(n + n·x) | O(1) | x = files removed |
| `distutils.errors` exception classes, `distutils.debug.DEBUG` | O(1) | O(1) | `DEBUG` is `DISTUTILS_DEBUG` as read at import |

## Rebuilding Only What Changed

The dependency checks compare modification times, so an up-to-date file costs a few `stat` calls
instead of a copy. `copy_file(update=1)` and the commands that copy files rely on them.

```python
import os
import tempfile
from distutils.dep_util import newer, newer_group
from distutils.file_util import copy_file

with tempfile.TemporaryDirectory() as tmp:
    src = os.path.join(tmp, 'module.py')
    dst = os.path.join(tmp, 'copy.py')
    with open(src, 'w') as f:
        f.write('x = 1\n')

    assert newer(src, dst)  # O(1) - the target does not exist
    assert copy_file(src, dst, update=1) == (dst, 1)  # O(b) - copied
    assert not newer(src, dst)  # the copy keeps the source's modification time
    assert copy_file(src, dst, update=1) == (dst, 0)  # O(1) - skipped

    os.utime(src, (2_000_000_000, 2_000_000_000))
    assert newer_group([src, dst], dst)  # O(n) - stops at the first newer source
```

### Compiling Is Not Incremental

`CCompiler.compile()` runs the compiler once per source on every call, so a build that calls
it directly recompiles everything. The link and archive steps do check timestamps.

```python
import os
import tempfile
from distutils.ccompiler import new_compiler

with tempfile.TemporaryDirectory() as tmp:
    sources = []
    for name in ('a.c', 'b.c', 'c.c'):
        path = os.path.join(tmp, name)
        with open(path, 'w') as f:
            f.write('int f(void) { return 0; }\n')
        sources.append(path)

    cc = new_compiler(compiler='unix')
    runs = []
    cc.spawn = runs.append  # record the commands instead of running them

    objects = cc.compile(sources, output_dir=os.path.join(tmp, 'build'))  # O(n) runs
    for obj in objects:  # stand in for the compiler's output
        with open(obj, 'w'):
            pass
        os.utime(obj, (1_000_000_000, 1_000_000_000))
    assert len(runs) == 3

    runs.clear()
    cc.compile(sources, output_dir=os.path.join(tmp, 'build'))  # every source again
    assert len(runs) == 3

    library = cc.library_filename('demo', output_dir=tmp)
    with open(library, 'w'):  # newer than every object
        pass
    runs.clear()
    cc.create_static_lib(objects, 'demo', output_dir=tmp)  # O(n) stats, no run
    assert runs == []
```

## Directories mkpath Has Seen

`mkpath()` records every directory it creates and skips a recorded one. A directory deleted by
anything other than `remove_tree()` is therefore not created again.

```python
import os
import shutil
import tempfile
from distutils.dir_util import mkpath, remove_tree

with tempfile.TemporaryDirectory() as tmp:
    build = os.path.join(tmp, 'build')
    target = os.path.join(build, 'lib')
    assert mkpath(target) == [build, target]  # O(d)

    shutil.rmtree(build)
    assert mkpath(target) == []  # remembered, so nothing is created
    assert not os.path.isdir(target)

    os.makedirs(target)
    remove_tree(build)  # O(n) - and forgets the directories it removed
    assert mkpath(target) == [build, target]
    assert os.path.isdir(target)
```

## Comparing Versions

Comparing a version against a string parses the string each time. Sort with the class as the
key so each string is parsed once.

```python
from distutils.version import LooseVersion, StrictVersion

releases = ['1.9', '1.10', '1.2b1', '1.2']
assert sorted(releases, key=StrictVersion) == ['1.2b1', '1.2', '1.9', '1.10']
assert sorted(releases, key=LooseVersion) == ['1.2', '1.2b1', '1.9', '1.10']

current = LooseVersion('1.9')
assert current < '1.10'  # O(L) - the string is parsed for this comparison

try:
    LooseVersion('1.0a') < LooseVersion('1.0.1')
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('mixed components compared without error')
```

## Common Patterns

### Standard Library Replacements

Python 3.12 and later have no `distutils`. These standard-library calls replace the most used
of its utility functions.

```python
import os
import shlex
import shutil
import sysconfig
import tempfile

assert shlex.split('cc -DNAME="a b" -O2') == ['cc', '-DNAME=a b', '-O2']  # split_quoted
assert shutil.which('no-such-program-here') is None  # find_executable
paths = sysconfig.get_paths()  # get_python_lib, get_python_inc
assert 'purelib' in paths and 'include' in paths

with tempfile.TemporaryDirectory() as tmp:
    src = os.path.join(tmp, 'src')
    os.makedirs(os.path.join(src, 'pkg'), exist_ok=True)  # mkpath
    with open(os.path.join(src, 'pkg', 'mod.py'), 'w') as f:
        f.write('x = 1\n')

    dst = os.path.join(tmp, 'dst')
    shutil.copytree(src, dst, dirs_exist_ok=True)  # copy_tree - O(n + b)
    archive = shutil.make_archive(os.path.join(tmp, 'dist'), 'gztar', root_dir=dst)
    assert archive.endswith('.tar.gz')  # make_archive - O(n + b)
```

## Performance Best Practices

✅ **Do**:

- Let the commands' timestamp checks skip up-to-date files, and pass `--force` only when a
  rebuild is really needed
- List the headers an `Extension` includes in its `depends`: `build_ext` compares only the
  sources and `depends` with the built extension, so a changed header is otherwise missed
- Sort versions with `key=LooseVersion` or `key=StrictVersion`, so each string is parsed once

❌ **Avoid**:

- Calling `CCompiler.compile()` in a loop expecting it to skip unchanged sources - it never does
- Deleting build directories with `shutil.rmtree()` and then relying on `mkpath()` to recreate
  them in the same process - use `remove_tree()`
- `make_archive()` with `root_dir` from a multithreaded program - it changes the working
  directory of the whole process

## Version Notes

- **Python 3.10+**: Importing the package emits a `DeprecationWarning` (PEP 632)
- **Python 3.11+**: `distutils.command.bdist_msi` removed
- **Python 3.12+**: Removed; `import distutils` raises `ModuleNotFoundError`

## Related Modules

- **[sysconfig](sysconfig.md)** - Python's build configuration and install paths, which
  `distutils.sysconfig` re-exports
- **[shutil](shutil.md)** - `copytree()`, `make_archive()` and `which()` replace `copy_tree()`,
  `make_archive()` and `find_executable()`
- **[compileall](compileall.md)** - byte-compiles a tree, as `byte_compile()` does a list
- **[shlex](shlex.md)** - `shlex.split()` splits a command line as `split_quoted()` does
- **[venv](venv.md)** - creates the isolated environments packages are installed into
