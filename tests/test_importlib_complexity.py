"""Tests for docs/stdlib/importlib.md.

The page prices importing as a `sys.modules` probe when the module is loaded
and a walk over path entries when it is not, each entry backed by a directory
listing that is cached by mtime; loading as a file read, an unmarshal or a
compile, and the module's own body; `importlib.metadata` as a directory
listing per path entry plus a file read per distribution; and
`importlib.resources` as O(1) on a file-system package with the costs that
zip archives, namespace packages and an omitted anchor add. Most rows are
settled by counting calls at the boundary the row names: a meta path finder,
`FileFinder.find_spec`, the bootstrap `listdir`, `source_to_code`,
`Distribution.read_text`, a loader's own methods. Where only a stopwatch
separates the growth classes, two sizes are timed and the ratio asserted.

Measurement scope:

* `import_module()` and `__import__()` on a loaded module return the object
  in `sys.modules` and call no meta path finder; a miss calls each finder
  once, in order, and stops at the first that returns a spec. A three-level
  dotted name runs each missing body once, top down, and none the second
  time. A relative name without `package` raises `TypeError`. `__import__()`
  with a `fromlist` consults no finder for names the package already has,
  imports a submodule it lacks, and expands `'*'` to `__all__`.
* `find_spec()` and `import_module()` on a miss call `FileFinder.find_spec`
  once per path entry: 10 and 100 extra directories differ by exactly 90
  calls, a module in the first directory costs one call, and a namespace
  package costs one call per entry on `sys.path`. Construction of a
  `FileFinder` calls the bootstrap `listdir` zero times, the first search
  once, the second none; a warm search calls the bootstrap `stat` once for
  the directory on a miss, once more for the candidate file on a hit, and
  once more for the `__init__` of a package directory. A file written
  behind an unchanged directory mtime
  is not found until `invalidate_caches()`, and relisting a directory of 10
  against 5,000 entries costs more than 20x in a timing test while a warm
  search costs under 5x. A warm miss on a finder registered with 2 against
  2,000 suffixes costs between 10x and 20,000x, the s term. `importlib.invalidate_caches()` calls
  `invalidate_caches()` once on each meta path finder that has one and once
  per `FileFinder` in `sys.path_importer_cache`, and drops the cache's
  relative and `None` entries.
* The first import of a source module calls `source_to_code` once and reads
  the `.pyc` path then the source; the second import in the same process
  reads only the `.pyc` and compiles nothing; a rewrite that keeps the size
  and the mtime is served stale from the `.pyc`; a changed mtime at the same
  size compiles again, and so does a changed size at the same mtime. `get_code()` from a valid `.pyc` over 2,000 and 40,000
  assignment lines costs more than 5x in a timing test. `cache_from_source()`
  and `source_from_cache()` round-trip a path that does not exist.
  `source_hash()` is 8 bytes and, over 100 KB against 10 MB, costs between
  10x and 1,000x, as does `decode_source()`, which also honours a coding
  declaration and turns CRLF into LF.
* `find_spec()` on a loaded module is its `__spec__` object and calls no
  finder; on an unloaded module it calls a meta path finder once, and the
  import that follows calls it once more; on a module whose body raises it
  returns the spec and leaves `sys.modules` untouched, and `module_from_spec()` builds the module with
  its attributes set without running the body. A dotted name imports the
  parent package and not the leaf, and raises `ModuleNotFoundError` when
  the parent is missing. `set_data()` creates three missing directories.
  `spec_from_file_location()` picks the
  loader by suffix with zero `stat()` or `listdir` calls and returns `None`
  for an unknown suffix; `spec_from_loader()` calls `is_package()` once when
  not told and never when told. `ModuleSpec.cached` is the same object on a
  second access, `parent` is the name for a package and its head otherwise.
* `LazyLoader.exec_module()` leaves a module whose body appends to a
  sentinel list untouched and reads and compiles nothing; the first
  attribute access reads the absent `.pyc` path and the source, compiles
  once and appends once, and the second does none of it again. `factory()` wraps a loader class.
* `reload()` re-runs the body of the module passed and not the body of a
  module it imports: bodies that count their own runs through `globals()`
  reach (2, 1) after one reload and (3, 1) after two.
* A namespace package's `__path__` gains a portion when `sys.path` gains
  one, without `invalidate_caches()`. A directory without `__init__.py` on
  the first entry loses to a regular module of the same name on the second. `NamespaceLoader` returns `''`, a code
  object, `True` and `None` from `get_source()`, `get_code()`,
  `is_package()` and `create_module()`.
* `InspectLoader.get_code()` calls `get_source()` and `source_to_code()` on
  every call and returns a fresh code object each time; `ExecutionLoader.get_code()` stamps
  `get_filename()` into it. A `SourceLoader` subclass's `get_code()` calls
  `path_stats()` once, `get_data()` on the cache path then the source,
  `source_to_code()` once and `set_data()` once with bytes that start with
  `MAGIC_NUMBER`; when `get_data()` returns the bytes just written, the
  second call reads no source and compiles nothing. Default methods return
  `None`, raise `ImportError` or `OSError` as the rows say, and the
  machinery classes are registered with the ABCs. `load_module()` warns
  `DeprecationWarning` and runs the body. `SourcelessFileLoader.get_code()`
  returns the code from a `.pyc` and `get_source()` `None`;
  `ExtensionFileLoader` returns `None` from `get_code()` and `get_source()`
  without loading. `BuiltinImporter` and `FrozenImporter` find a built-in
  and a frozen module and not a source one.
* `files()` on an imported package is a `pathlib.Path`, and on a name a
  package whose body, counting its runs through `globals()`, runs once
  across two calls. With no anchor, on 3.12+, calling from a
  recursion 50 and 1,500 frames deep costs between 6x and 600x in a timing
  test.
  With no anchor the recursion itself is measured with an anchored call at
  the same depth and subtracted. On a zip archive `files()` reads the
  central directory (`ZipFile`'s contents read) once per call and none per
  `joinpath()`; over archives of 10 and 3,000 entries `files()` costs more
  than 15x in a timing test while `joinpath()` on a held, already probed
  result costs under 4x and `iterdir()` more than 15x. Every growth ratio
  also carries an upper bound below what a quadratic would give. `as_file()` yields a
  file-system path as the same object and a zip resource as a temporary file
  with equal bytes that is gone afterwards.
* A namespace package's `MultiplexedPath.joinpath()` over portions holding
  10 and 2,000 children costs between 20x and 4,000x in a timing test,
  which admits the O(k log k) sort from 3.12, the O(k) walk of 3.11 and,
  at these sizes, the O(k²) list scan of 3.10, whose constant is small; the
  three are separated by reading Lib/importlib/readers.py and
  Lib/importlib/resources/readers.py, not by the ratio, as is the early
  stop at the first match that 3.10 and 3.11 take and 3.12's sort forgoes:
  the timed target always sits in the second portion. Every test builds
  exactly two portions, so the r term, a listing per portion, empty or
  not, is read from the same files and not varied. `iterdir()` merges the portions
  by name, a name present in both portions appearing once and
  resolving to the first portion's file: from 3.12 the names come out
  sorted, and before it every name of the first portion precedes every name
  of the second. The default `Traversable.joinpath()` (3.12+)
  calls `iterdir()` once on each directory a segment passes through. The
  functional API returns what `files().joinpath()` does and, from 3.11,
  calls `files()` once per call, so two `read_text()` calls resolve the
  anchor twice; 3.10 resolves the package by another route and is not
  counted. `contents()` is a list before 3.13 and an iterator from it, and warns
  `DeprecationWarning` on 3.11+, and `TraversableResources` resolves
  `open_resource()`, `is_resource()` and `contents()` through `files()`
  while `resource_path()` raises `FileNotFoundError`.
* `distribution()` calls `PathDistribution.read_text` zero times;
  `version()` once, twice for two calls; `dist.version` then `dist.name`
  once each; `dist.files`, `dist.entry_points` and `dist.origin` twice for
  two accesses on one object. `Distribution.at()` reads nothing. `distributions()` calls
  `os.listdir` once per path entry the first time it is consumed, not at
  all the second time, again after `importlib.invalidate_caches()` from
  3.11 and `MetadataPathFinder.invalidate_caches()` on 3.10,
  and again, without it, once a new `.dist-info` directory has changed the
  entry's mtime;
  that the cache behind this holds 128 path entries is the `lru_cache` on
  `FastPath.__new__` in Lib/importlib/metadata/__init__.py, not exercised.
* `entry_points(group=...)` reads `entry_points.txt` once per distribution:
  sites of 5 and 50 fake distributions differ by exactly 45 reads. That
  3.10 and 3.11 sort the entry points by group first is read from
  Lib/importlib/metadata/__init__.py's `SelectableGroups.load()`, not timed.
  That `set_data()` writes its buffer straight through a temporary file is
  read from `_write_atomic` in Lib/importlib/_bootstrap_external.py.
  `EntryPoints` of 100 and 20,000 entries cost more than 40x in a timing
  test for `select()`, `names` and `[name]` on the first entry, which an
  early-exit scan would find in O(1), and `[0]` raises `KeyError` from 3.12
  and warns before. `packages_distributions()` reads `top_level.txt` and
  not `RECORD` for a distribution that has one, and `RECORD` for one that
  does not from 3.11; 3.10 reads only `top_level.txt`.
* `Distribution.files` returns only entries whose file exists on 3.12+,
  calling `Path.exists()` once per entry, and every entry before 3.12.
  `metadata['Version']` over 100 and 3,000 headers costs between 5x and
  120x in a timing test and `metadata.json` between 200x and 5,000x, which
  separates the linear scan from the quadratic one and that from a cubic.
* Version boundaries are asserted by presence: `find_loader()`,
  `abc.Finder` and the `util` decorators exist below 3.12,
  `resources.abc` and `NamespaceLoader` from 3.11, `abc.Traversable` below
  3.14, `Distribution.origin` and `AppleFrameworkLoader` from 3.13,
  `_incompatible_extension_module_restrictions` from 3.12, `entry_points()`
  with no selector returns a `dict` below 3.12, `files()` on a plain module
  raises `TypeError` below 3.12, `Anchor` exists from 3.12, `EntryPoints`
  is a `list` below 3.12 and a `tuple` from it, `EntryPoint` indexes silently
  on 3.10 and with a warning on 3.11 and 3.12, the functional API warns from
  3.11 until 3.12.10, `contents()` then again from 3.13, several path names
  reach the functional API in 3.13 and raise `TypeError` before, and
  `DEBUG_BYTECODE_SUFFIXES` and `SourceLoader.path_mtime()` warn from
  3.14.
* Every fenced Python block runs in its own subprocess and working
  directory, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* `WindowsRegistryFinder.find_spec()` is Windows-only and
  `AppleFrameworkLoader` iOS-only; neither row is verified by a run this
  project performs. `ExtensionFileLoader.create_module()` is a dynamic
  library load that no Python-level counter sees; the test shows only that
  the finder-side methods load nothing.
* The O(b) and O(f) scans of the built-in and frozen tables are read from
  Python/import.c; the tables are fixed per build and cannot be varied.
* `ModuleSpec`, `LazyLoader.factory()`, `Anchor`, `Package`,
  `PackageMetadata` as a protocol and `DistributionFinder.Context` are
  attribute holders whose O(1) is definitional, as is subclassing an ABC.
  That `files()` on a namespace package checks each portion, that a
  `MultiplexedPath` segment resolved to one directory joins the rest as a
  plain path, and that `packages_distributions()` holds a distribution's
  `files` list and parsed `METADATA` while it works are read from
  Lib/importlib/resources/readers.py and Lib/importlib/metadata/__init__.py.
* `importlib.readers`, `importlib.simple`, `importlib.resources.readers`,
  `importlib.resources.simple` and the `importlib.metadata` helpers
  (`FastPath`, `Lookup`, `Prepared`, `Sectioned`, `Pair`, `FileHash`,
  `FreezableDefaultDict`, `DeprecatedNonAbstract`, `SimplePath`,
  `diagnose`) are undocumented internals and are left off the page on
  purpose. `Loader.exec_module()`, `MetaPathFinder.find_spec()` and
  `PathEntryFinder.find_spec()` are documented but defined by no ABC, so
  the audit cannot resolve them on any interpreter.
* `as_file()` on a directory inside a zip archive copies the tree (3.12+),
  read from Lib/importlib/resources/_common.py and not measured. That the
  first probe of a held `zipfile.Path` indexes the archive's names, O(z),
  once is read from Lib/zipfile/_path/__init__.py; the timing test takes
  the fastest of repeated probes, so it measures the probes after it.
* Hash-based `.pyc` files, which under the default `--check-hash-based-pycs`
  policy are validated by hashing the source when checked and trusted as
  they are when not, are not produced here; only timestamp-based caches
  are exercised under the default policy.
* Compilation and unmarshalling are taken as linear in the bytes they
  consume; the `get_code()` timing shows growth between linear and
  quadratic, not the constant. That `EntryPoint.module`, `attr` and
  `extras` run the regex per access, that `PathFinder.invalidate_caches()`
  snapshots `sys.path_importer_cache` and that `packages_distributions()`
  parses `METADATA` once per declared name are read from
  Lib/importlib/metadata/__init__.py and Lib/importlib/_bootstrap_external.py.
* Pricing `METADATA` parsing in headers treats each value and the
  description body as O(1); values are not varied in length. Only
  `.dist-info` distributions with `RECORD` and `Requires-Dist` headers are
  built; the egg-info fallbacks (`requires.txt`, `installed-files.txt`,
  `SOURCES.txt`) are priced from Lib/importlib/metadata/__init__.py and
  not exercised. A path
  entry that does not exist is relisted on every `distributions()` call,
  since its missing mtime clears the listing cache; only existing entries
  are asserted listed once.
* Path lengths, name lengths and the size of `sys.meta_path` are not varied.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.resources
import importlib.util
import os
import pathlib
import py_compile
import re
import subprocess
import sys
import sysconfig
import textwrap
import time
import types
import warnings
import zipfile
from collections.abc import Callable, Iterator
from importlib.machinery import FileFinder, ModuleSpec, SourceFileLoader
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "importlib.md"
EXPECTED_BLOCKS = 15

bootstrap_external: Any = importlib.import_module("importlib._bootstrap_external")
metadata_path_finder: Any = importlib.metadata.MetadataPathFinder
resources_abc: Any = (
    importlib.import_module("importlib.resources.abc")
    if sys.version_info >= (3, 11)
    else importlib.abc
)


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


@pytest.fixture(autouse=True)
def import_state() -> Iterator[None]:
    """Restore the import system's shared state after every test."""
    path = list(sys.path)
    meta_path = list(sys.meta_path)
    modules = set(sys.modules)
    importer_cache = dict(sys.path_importer_cache)
    zip_cache: Any = importlib.import_module("zipimport")._zip_directory_cache
    archives = set(zip_cache)
    yield
    sys.path[:] = path
    sys.meta_path[:] = meta_path
    stdlib = sysconfig.get_paths()["stdlib"]
    for name in set(sys.modules) - modules:
        origin = getattr(getattr(sys.modules[name], "__spec__", None), "origin", None)
        if origin is None or not str(origin).startswith(stdlib):
            del sys.modules[name]
    importlib.invalidate_caches()
    sys.path_importer_cache.clear()
    sys.path_importer_cache.update(importer_cache)
    for archive in set(zip_cache) - archives:
        del zip_cache[archive]
    metadata_path_finder().invalidate_caches()


def write_module(directory: pathlib.Path, name: str, source: str) -> pathlib.Path:
    path = directory / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    return path


def make_dist(
    site: pathlib.Path,
    name: str,
    *,
    version: str = "1.0",
    entry_points: str | None = None,
    record: str | None = None,
    top_level: str | None = None,
    extra_metadata: str = "",
) -> pathlib.Path:
    info = site / f"{name}-{version}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n{extra_metadata}",
        encoding="utf-8",
    )
    if entry_points is not None:
        (info / "entry_points.txt").write_text(entry_points, encoding="utf-8")
    if record is not None:
        (info / "RECORD").write_text(record, encoding="utf-8")
    if top_level is not None:
        (info / "top_level.txt").write_text(top_level, encoding="utf-8")
    return info


class CountingFinder:
    """A meta path finder that counts its calls and finds nothing."""

    def __init__(self, events: list[tuple[str, str]] | None = None, label: str = "") -> None:
        self.calls: list[str] = []
        self.invalidations = 0
        self.events = events
        self.label = label

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        self.calls.append(fullname)
        if self.events is not None:
            self.events.append((self.label, fullname))
        return None

    def invalidate_caches(self) -> None:
        self.invalidations += 1


class RecordingLoader(importlib.abc.Loader):
    """A loader whose module body appends its name to `runs`."""

    def __init__(self, runs: list[str]) -> None:
        self.runs = runs

    def exec_module(self, module: types.ModuleType) -> None:
        self.runs.append(module.__name__)


class TestImportModuleIsACacheLookup:
    """`import_module()` | O(1) | O(1) for a loaded module.

    A counting finder on `sys.meta_path` separates a `sys.modules` hit, which
    consults no finder, from a miss, which consults each finder once.
    """

    def test_a_loaded_module_is_the_same_object_and_consults_no_finder(self) -> None:
        import json
        import json.decoder

        finder = CountingFinder()
        sys.meta_path.insert(0, finder)

        assert importlib.import_module("json") is json
        assert importlib.import_module("json.decoder") is json.decoder
        assert importlib.__import__("json") is json
        assert finder.calls == []

    def test_a_miss_consults_each_finder_once_in_order(self) -> None:
        events: list[tuple[str, str]] = []
        front, back = CountingFinder(events, "front"), CountingFinder(events, "back")
        sys.meta_path.insert(0, front)
        sys.meta_path.append(back)

        with pytest.raises(ModuleNotFoundError) as info:
            importlib.import_module("no_such_module_anywhere")

        assert info.value.name == "no_such_module_anywhere"
        assert events == [("front", "no_such_module_anywhere"), ("back", "no_such_module_anywhere")]

    def test_the_search_stops_at_the_first_finder_that_answers(self) -> None:
        runs: list[str] = []
        loader = RecordingLoader(runs)

        class Answering:
            @staticmethod
            def find_spec(fullname: str, path: Any = None, target: Any = None) -> Any:
                return ModuleSpec(fullname, loader) if fullname == "answered_here" else None

        back = CountingFinder()
        sys.meta_path.insert(0, Answering)
        sys.meta_path.append(back)

        module = importlib.import_module("answered_here")

        assert module is sys.modules["answered_here"]
        assert runs == ["answered_here"]
        assert back.calls == []

    def test_a_dotted_name_runs_each_missing_body_once_top_down(
        self, tmp_path: pathlib.Path
    ) -> None:
        sentinel = types.ModuleType("dotted_sentinel")
        sentinel.RUNS = []  # type: ignore[attr-defined]
        sys.modules["dotted_sentinel"] = sentinel
        (tmp_path / "dpkg" / "dsub").mkdir(parents=True)
        for path, name in (("dpkg", "dpkg"), ("dpkg/dsub", "dpkg.dsub")):
            write_module(
                tmp_path / path,
                "__init__",
                f"import dotted_sentinel\ndotted_sentinel.RUNS.append({name!r})\n",
            )
        write_module(
            tmp_path / "dpkg" / "dsub",
            "leaf",
            "import dotted_sentinel\ndotted_sentinel.RUNS.append('leaf')\n",
        )
        sys.path.insert(0, str(tmp_path))

        leaf = importlib.import_module("dpkg.dsub.leaf")
        assert sentinel.RUNS == ["dpkg", "dpkg.dsub", "leaf"]  # type: ignore[attr-defined]

        assert importlib.import_module("dpkg.dsub.leaf") is leaf
        assert sentinel.RUNS == ["dpkg", "dpkg.dsub", "leaf"]  # type: ignore[attr-defined]

    def test_a_relative_name_needs_a_package(self) -> None:
        with pytest.raises(TypeError):
            importlib.import_module(".decoder")
        import json.decoder

        assert importlib.import_module(".decoder", "json") is json.decoder

    def test_dunder_import_imports_fromlist_names_as_submodules(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "fpkg").mkdir()
        write_module(tmp_path / "fpkg", "__init__", "")
        write_module(tmp_path / "fpkg", "leaf", "VALUE = 1\n")
        write_module(tmp_path / "fpkg", "other", "VALUE = 2\n")
        sys.path.insert(0, str(tmp_path))

        top = importlib.__import__("fpkg.leaf")
        assert top.__name__ == "fpkg" and top.leaf.VALUE == 1
        assert "fpkg.other" not in sys.modules

        package = importlib.__import__("fpkg", fromlist=["other"])
        assert package is top and package.other.VALUE == 2
        assert "fpkg.other" in sys.modules

        write_module(tmp_path / "fpkg", "starred", "VALUE = 3\n")
        namespace: Any = top
        namespace.__all__ = ["starred"]
        namespace.PRESENT = object()
        finder = CountingFinder()
        sys.meta_path.insert(0, finder)
        assert importlib.__import__("fpkg", fromlist=["PRESENT", "leaf"]) is top
        assert finder.calls == []
        assert importlib.__import__("fpkg", fromlist=["*"]) is top
        assert finder.calls == ["fpkg.starred"] and top.starred.VALUE == 3


class TestAMissWalksThePath:
    """`PathFinder.find_spec()` | O(p·s): one path entry finder per entry,
    stopping at the first hit, and every entry for a namespace package.

    Counted at `FileFinder.find_spec`, which every directory on `sys.path`
    reaches through the class attribute.
    """

    @pytest.fixture
    def counted(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []
        original = FileFinder.find_spec

        def counting(self: FileFinder, fullname: str, target: Any = None) -> Any:
            calls.append(self.path)
            return original(self, fullname, target)

        monkeypatch.setattr(FileFinder, "find_spec", counting)
        return calls

    @staticmethod
    def _directories(tmp_path: pathlib.Path, count: int) -> list[str]:
        directories = [tmp_path / f"entry{index}" for index in range(count)]
        for directory in directories:
            directory.mkdir()
        return [str(directory) for directory in directories]

    def test_a_miss_costs_one_finder_call_per_path_entry(
        self, tmp_path: pathlib.Path, counted: list[str]
    ) -> None:
        counts: dict[int, int] = {}
        for size in (10, 100):
            entries = (
                self._directories(tmp_path / str(size), size)
                if (tmp_path / str(size)).mkdir() is None
                else []
            )
            sys.path[:0] = entries
            counted.clear()
            assert importlib.util.find_spec("no_such_module_anywhere") is None
            counts[size] = len(counted)
            del sys.path[:size]

        assert counts[100] - counts[10] == 90, counts

    def test_a_hit_in_the_first_entry_costs_one_call(
        self, tmp_path: pathlib.Path, counted: list[str]
    ) -> None:
        entries = self._directories(tmp_path, 10)
        write_module(pathlib.Path(entries[0]), "first_hit", "WHERE = 0\n")
        write_module(pathlib.Path(entries[9]), "first_hit", "WHERE = 9\n")
        sys.path[:0] = entries

        spec = importlib.util.find_spec("first_hit")

        assert spec is not None and spec.origin == str(pathlib.Path(entries[0], "first_hit.py"))
        assert counted == [entries[0]]
        assert importlib.import_module("first_hit").WHERE == 0

    def test_a_namespace_package_visits_every_entry(
        self, tmp_path: pathlib.Path, counted: list[str]
    ) -> None:
        entries = self._directories(tmp_path, 10)
        (pathlib.Path(entries[0]) / "walked_ns").mkdir()
        sys.path[:0] = entries
        directories_on_path = [entry for entry in sys.path if os.path.isdir(entry or os.getcwd())]

        package = importlib.import_module("walked_ns")

        assert package.__file__ is None
        assert len(counted) >= len(entries)
        assert counted[: len(entries)] == entries
        assert len(counted) == len(directories_on_path)


class TestDirectoryListingsAreCachedByMtime:
    """`FileFinder.find_spec()` | O(s), and O(e) to relist when the mtime
    changed; `invalidate_caches()` forgets the mtime.

    The bootstrap module's own `listdir` is counted, and a file is hidden by
    restoring the directory's mtime after writing it.
    """

    @pytest.fixture
    def listdir_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []
        original = bootstrap_external._os.listdir

        def counting(path: Any = None) -> Any:
            calls.append(str(path))
            return original(path) if path is not None else original()

        monkeypatch.setattr(bootstrap_external._os, "listdir", counting)
        return calls

    def test_construction_lists_nothing_and_the_first_search_lists_once(
        self, tmp_path: pathlib.Path, listdir_calls: list[str]
    ) -> None:
        finder = FileFinder(str(tmp_path), (SourceFileLoader, [".py"]))
        assert listdir_calls == []

        assert finder.find_spec("nothing") is None
        assert listdir_calls == [str(tmp_path)]

        assert finder.find_spec("nothing_else") is None
        assert listdir_calls == [str(tmp_path)]

    def test_a_warm_search_stats_the_directory_and_each_candidate(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stats: list[str] = []
        original = bootstrap_external._os.stat

        def counting(path: Any, *args: Any, **kwargs: Any) -> Any:
            stats.append(os.path.basename(str(path)))
            return original(path, *args, **kwargs)

        write_module(tmp_path, "present", "")
        (tmp_path / "package").mkdir()
        write_module(tmp_path / "package", "__init__", "")
        finder = FileFinder(str(tmp_path), (SourceFileLoader, [".py", ".pyw"]))
        finder.find_spec("nothing")
        monkeypatch.setattr(bootstrap_external._os, "stat", counting)

        assert finder.find_spec("nothing") is None
        assert stats == [tmp_path.name]

        stats.clear()
        assert finder.find_spec("present") is not None
        assert stats == [tmp_path.name, "present.py"]

        stats.clear()
        assert finder.find_spec("package") is not None
        assert stats == [tmp_path.name, "__init__.py"]

    def test_a_file_hidden_behind_the_mtime_is_found_only_after_invalidation(
        self, tmp_path: pathlib.Path
    ) -> None:
        finder = FileFinder(str(tmp_path), (SourceFileLoader, [".py"]))
        assert finder.find_spec("late") is None

        stat = os.stat(tmp_path)
        write_module(tmp_path, "late", "X = 1\n")
        os.utime(tmp_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert finder.find_spec("late") is None

        finder.invalidate_caches()
        spec = finder.find_spec("late")
        assert spec is not None and spec.origin == str(tmp_path / "late.py")

    @pytest.mark.timing
    def test_relisting_costs_the_directory_size_and_a_warm_search_does_not(
        self, tmp_path: pathlib.Path
    ) -> None:
        relist: dict[int, float] = {}
        warm: dict[int, float] = {}
        for size in (10, 5_000):
            directory = tmp_path / str(size)
            directory.mkdir()
            for index in range(size):
                (directory / f"entry{index}.txt").write_bytes(b"")
            finder = FileFinder(str(directory), (SourceFileLoader, [".py"]))
            finder.find_spec("nothing")

            def relisted(finder: FileFinder = finder) -> None:
                finder.invalidate_caches()
                finder.find_spec("nothing")

            relist[size] = best_ns(relisted)
            warm[size] = best_ns(lambda finder=finder: finder.find_spec("nothing"), 15)

        relist_ratio = relist[5_000] / relist[10]
        warm_ratio = warm[5_000] / warm[10]
        assert 20 < relist_ratio < 50_000, (
            f"relisting 5,000 entries cost {relist_ratio:.1f}x 10 entries"
        )
        assert warm_ratio < 5, f"a warm search over 5,000 entries cost {warm_ratio:.1f}x 10 entries"

    @pytest.mark.timing
    def test_a_warm_search_follows_the_suffix_count(self, tmp_path: pathlib.Path) -> None:
        costs: dict[int, float] = {}
        for suffixes in (2, 2_000):
            details = (SourceFileLoader, [f".s{index}" for index in range(suffixes)])
            finder = FileFinder(str(tmp_path), details)
            finder.find_spec("nothing")
            costs[suffixes] = best_ns(lambda finder=finder: finder.find_spec("nothing"))

        ratio = costs[2_000] / costs[2]
        assert 10 < ratio < 20_000, f"1,000x the suffixes cost a warm search {ratio:.1f}x"

    def test_invalidate_caches_reaches_every_meta_path_and_cached_finder(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sys.path.insert(0, str(tmp_path))
        assert importlib.util.find_spec("no_such_module_anywhere") is None
        meta = CountingFinder()
        sys.meta_path.append(meta)
        cached = [
            finder for finder in sys.path_importer_cache.values() if isinstance(finder, FileFinder)
        ]
        assert any(finder.path == str(tmp_path) for finder in cached)
        invalidated: list[str] = []
        monkeypatch.setattr(
            FileFinder, "invalidate_caches", lambda self: invalidated.append(self.path)
        )
        sys.path_importer_cache["relative_entry"] = None
        sys.path_importer_cache[str(tmp_path / "absent")] = None

        importlib.invalidate_caches()

        assert meta.invalidations == 1
        assert sorted(invalidated) == sorted(finder.path for finder in cached)
        assert "relative_entry" not in sys.path_importer_cache
        assert str(tmp_path / "absent") not in sys.path_importer_cache


class TestBytecodeCaching:
    """`SourceFileLoader.get_code()` | O(n): the `.pyc` when its recorded
    mtime and size match, otherwise a compile and a cache write.

    `source_to_code` and `FileLoader.get_data` are counted through the class
    attributes the loader instances reach them by.
    """

    @pytest.fixture
    def counters(self, monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
        compiled: list[str] = []
        read: list[str] = []
        original_compile = SourceFileLoader.source_to_code
        original_read = bootstrap_external.FileLoader.get_data

        def counting_compile(self: Any, data: Any, path: Any, *args: Any, **kwargs: Any) -> Any:
            compiled.append(os.path.basename(str(path)))
            return original_compile(self, data, path, *args, **kwargs)

        def counting_read(self: Any, path: Any) -> Any:
            read.append(os.path.basename(str(path)))
            return original_read(self, path)

        monkeypatch.setattr(SourceFileLoader, "source_to_code", counting_compile)
        monkeypatch.setattr(bootstrap_external.FileLoader, "get_data", counting_read)
        return compiled, read

    def test_the_first_import_compiles_and_the_second_unmarshals(
        self, tmp_path: pathlib.Path, counters: tuple[list[str], list[str]]
    ) -> None:
        compiled, read = counters
        source = write_module(tmp_path, "cached_mod", "VALUE = 1\n")
        os.utime(source, (1_000_000_000, 1_000_000_000))
        sys.path.insert(0, str(tmp_path))
        pyc = os.path.basename(importlib.util.cache_from_source(str(source)))

        module = importlib.import_module("cached_mod")
        assert module.VALUE == 1 and module.__cached__ == importlib.util.cache_from_source(
            str(source)
        )
        assert compiled == ["cached_mod.py"]
        assert read == [pyc, "cached_mod.py"]

        del sys.modules["cached_mod"]
        compiled.clear()
        read.clear()
        assert importlib.import_module("cached_mod").VALUE == 1
        assert compiled == []
        assert read == [pyc]

        del sys.modules["cached_mod"]
        compiled.clear()
        read.clear()
        source.write_text("VALUE = 3\n", encoding="utf-8")
        os.utime(source, (1_000_000_000, 1_000_000_000))
        assert importlib.import_module("cached_mod").VALUE == 1
        assert compiled == [] and read == [pyc]

        del sys.modules["cached_mod"]
        read.clear()
        os.utime(source, (1_000_000_100, 1_000_000_100))
        assert importlib.import_module("cached_mod").VALUE == 3
        assert compiled == ["cached_mod.py"]
        assert read == [pyc, "cached_mod.py"]

        del sys.modules["cached_mod"]
        compiled.clear()
        read.clear()
        source.write_text("VALUE = 22\n", encoding="utf-8")
        os.utime(source, (1_000_000_100, 1_000_000_100))
        assert importlib.import_module("cached_mod").VALUE == 22
        assert compiled == ["cached_mod.py"]
        assert read == [pyc, "cached_mod.py"]

    @pytest.mark.timing
    def test_get_code_from_a_valid_pyc_follows_the_file_size(self, tmp_path: pathlib.Path) -> None:
        costs: dict[int, float] = {}
        for lines in (2_000, 40_000):
            source = write_module(
                tmp_path, f"sized{lines}", "".join(f"x{i} = {i}\n" for i in range(lines))
            )
            loader = SourceFileLoader(f"sized{lines}", str(source))
            loader.get_code(f"sized{lines}")
            costs[lines] = best_ns(
                lambda loader=loader, lines=lines: loader.get_code(f"sized{lines}")
            )

        ratio = costs[40_000] / costs[2_000]
        assert 5 < ratio < 200, f"20x the source cost {ratio:.1f}x from the bytecode cache"

    def test_set_data_creates_the_missing_directories(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "made" / "on" / "demand" / "mod.pyc"
        SourceFileLoader("mod", str(tmp_path / "mod.py")).set_data(str(target), b"payload")
        assert target.read_bytes() == b"payload"

    def test_cache_paths_round_trip_without_the_files(self, tmp_path: pathlib.Path) -> None:
        source = str(tmp_path / "absent" / "mod.py")
        cached = importlib.util.cache_from_source(source)

        assert cached.startswith(str(tmp_path / "absent" / "__pycache__" / "mod."))
        assert cached.endswith(importlib.machinery.BYTECODE_SUFFIXES[0])
        assert importlib.util.source_from_cache(cached) == source
        with pytest.raises(ValueError):
            importlib.util.source_from_cache(source)

    def test_source_hash_is_eight_bytes(self) -> None:
        assert len(importlib.util.source_hash(b"x = 1\n")) == 8
        assert importlib.util.source_hash(b"x = 1\n") == importlib.util.source_hash(b"x = 1\n")
        assert importlib.util.source_hash(b"x = 1\n") != importlib.util.source_hash(b"x = 2\n")

    @pytest.mark.timing
    def test_source_hash_and_decode_source_follow_the_bytes(self) -> None:
        small, large = b"x = 1\n" * 17_000, b"x = 1\n" * 1_700_000
        hash_ratio = best_ns(lambda: importlib.util.source_hash(large)) / best_ns(
            lambda: importlib.util.source_hash(small)
        )
        decode_ratio = best_ns(lambda: importlib.util.decode_source(large), 3) / best_ns(
            lambda: importlib.util.decode_source(small), 3
        )
        assert 10 < hash_ratio < 1_000, f"100x the bytes hashed in {hash_ratio:.1f}x"
        assert 10 < decode_ratio < 1_000, f"100x the bytes decoded in {decode_ratio:.1f}x"

    def test_decode_source_honours_the_declaration_and_newlines(self) -> None:
        latin = "# coding: latin-1\r\nname = 'café'\r\n".encode("latin-1")
        assert importlib.util.decode_source(latin) == "# coding: latin-1\nname = 'café'\n"
        assert importlib.util.decode_source(b"x = 1\r\ny = 2") == "x = 1\ny = 2"


class TestFindingWithoutLoading:
    """`find_spec()` | O(1) for a loaded module, its own `__spec__`; otherwise
    a search that does not execute what it finds. `module_from_spec()`,
    `spec_from_file_location()` and `spec_from_loader()` read nothing."""

    def test_a_loaded_module_returns_its_own_spec_and_consults_no_finder(self) -> None:
        import json

        finder = CountingFinder()
        sys.meta_path.insert(0, finder)

        assert importlib.util.find_spec("json") is json.__spec__
        assert finder.calls == []

    def test_the_import_after_a_find_searches_again(self, tmp_path: pathlib.Path) -> None:
        write_module(tmp_path, "searched_twice", "")
        sys.path.insert(0, str(tmp_path))
        finder = CountingFinder()
        sys.meta_path.insert(0, finder)

        assert importlib.util.find_spec("searched_twice") is not None
        assert finder.calls == ["searched_twice"]
        importlib.import_module("searched_twice")
        assert finder.calls == ["searched_twice", "searched_twice"]
        importlib.import_module("searched_twice")
        assert finder.calls == ["searched_twice", "searched_twice"]

    def test_a_module_whose_body_raises_is_found_and_not_run(self, tmp_path: pathlib.Path) -> None:
        write_module(tmp_path, "explosive", "raise RuntimeError('body ran')\n")
        sys.path.insert(0, str(tmp_path))

        spec = importlib.util.find_spec("explosive")

        assert spec is not None and spec.origin == str(tmp_path / "explosive.py")
        assert "explosive" not in sys.modules
        assert importlib.util.find_spec("no_such_module_anywhere") is None

    def test_a_dotted_name_imports_the_parent_and_not_the_leaf(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "parent_pkg").mkdir()
        write_module(tmp_path / "parent_pkg", "__init__", "")
        write_module(tmp_path / "parent_pkg", "leaf", "raise RuntimeError('leaf ran')\n")
        sys.path.insert(0, str(tmp_path))

        spec = importlib.util.find_spec("parent_pkg.leaf")

        assert spec is not None and spec.name == "parent_pkg.leaf"
        assert "parent_pkg" in sys.modules and "parent_pkg.leaf" not in sys.modules
        with pytest.raises(ModuleNotFoundError):
            importlib.util.find_spec("no_such_package_anywhere.child")

    def test_module_from_spec_sets_attributes_and_calls_create_module_once(self) -> None:
        created: list[Any] = []

        class Loader(importlib.abc.Loader):
            def create_module(self, spec: ModuleSpec) -> None:
                created.append(spec)
                return None

            def exec_module(self, module: types.ModuleType) -> None:
                raise AssertionError("exec_module must not run")

        loader = Loader()
        spec = importlib.util.spec_from_loader("made_by_spec", loader)
        assert spec is not None

        module = importlib.util.module_from_spec(spec)

        assert created == [spec]
        assert module.__name__ == "made_by_spec"
        assert module.__spec__ is spec and module.__loader__ is loader
        assert module.__package__ == ""
        assert "made_by_spec" not in sys.modules

    def test_spec_from_file_location_picks_the_loader_by_suffix_without_io(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        touched: list[str] = []
        monkeypatch.setattr(bootstrap_external._os, "stat", lambda *a, **k: touched.append("stat"))
        monkeypatch.setattr(
            bootstrap_external._os, "listdir", lambda *a, **k: touched.append("listdir")
        )
        location = str(tmp_path / "absent.py")

        spec = importlib.util.spec_from_file_location("absent", location)

        assert spec is not None
        assert isinstance(spec.loader, SourceFileLoader)
        assert spec.origin == location and spec.has_location
        assert spec.submodule_search_locations is None
        assert (
            importlib.util.spec_from_file_location("absent", str(tmp_path / "absent.txt")) is None
        )
        assert touched == []

    def test_spec_from_loader_asks_is_package_only_when_not_told(self) -> None:
        asked: list[str] = []

        class Loader(importlib.abc.Loader):
            def is_package(self, fullname: str) -> bool:
                asked.append(fullname)
                return True

        spec = importlib.util.spec_from_loader("asked", Loader())
        assert spec is not None and spec.submodule_search_locations == []
        assert asked == ["asked"]

        spec = importlib.util.spec_from_loader("told", Loader(), is_package=False)
        assert spec is not None and spec.submodule_search_locations is None
        assert asked == ["asked"]

    def test_resolve_name_strips_one_level_per_dot(self) -> None:
        name = "absolute"
        assert importlib.util.resolve_name(name, None) is name
        assert importlib.util.resolve_name(".leaf", "pkg.sub") == "pkg.sub.leaf"
        assert importlib.util.resolve_name("..leaf", "pkg.sub") == "pkg.leaf"
        assert importlib.util.resolve_name("..", "pkg.sub") == "pkg"
        with pytest.raises(ImportError):
            importlib.util.resolve_name("...leaf", "pkg.sub")
        with pytest.raises(ImportError):
            importlib.util.resolve_name(".leaf", None)

    def test_module_spec_attributes(self, tmp_path: pathlib.Path) -> None:
        located = importlib.util.spec_from_file_location("a.b.c", str(tmp_path / "c.py"))
        assert located is not None
        assert located.cached == importlib.util.cache_from_source(str(tmp_path / "c.py"))
        assert located.cached is located.cached
        assert located.parent == "a.b"

        bare = ModuleSpec("a.b.c", None)
        assert bare.cached is None and not bare.has_location and bare.parent == "a.b"
        package = ModuleSpec("a.b.c", None, is_package=True)
        assert package.submodule_search_locations == [] and package.parent == "a.b.c"
        assert ModuleSpec("x", None, origin="o") == ModuleSpec("x", None, origin="o")
        assert ModuleSpec("x", None, origin="o") != ModuleSpec("x", None, origin="p")


class TestLazyLoaderDefersTheBody:
    """`LazyLoader.exec_module()` | O(1): the wrapped loader runs on the first
    attribute access. A sentinel module records when the body runs, since
    any attribute of the lazy module, `__dict__` included, would load it."""

    @pytest.fixture
    def sentinel(self) -> types.ModuleType:
        module = types.ModuleType("lazy_sentinel")
        module.RUNS = []  # type: ignore[attr-defined]
        sys.modules["lazy_sentinel"] = module
        return module

    def test_the_first_attribute_access_reads_and_runs_the_body_once(
        self, tmp_path: pathlib.Path, sentinel: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        write_module(
            tmp_path,
            "lazy_target",
            "import lazy_sentinel\nlazy_sentinel.RUNS.append(1)\nVALUE = 42\n",
        )
        sys.path.insert(0, str(tmp_path))
        spec = importlib.util.find_spec("lazy_target")
        assert spec is not None and spec.loader is not None
        spec.loader = importlib.util.LazyLoader(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules["lazy_target"] = module
        touched: list[str] = []
        read = bootstrap_external.FileLoader.get_data
        compile_source = SourceFileLoader.source_to_code
        monkeypatch.setattr(
            bootstrap_external.FileLoader,
            "get_data",
            lambda self, path: touched.append("read") or read(self, path),
        )
        monkeypatch.setattr(
            SourceFileLoader,
            "source_to_code",
            lambda self, data, path, *a, **k: (
                touched.append("compile") or compile_source(self, data, path, *a, **k)
            ),
        )

        spec.loader.exec_module(module)
        assert sentinel.RUNS == [] and touched == []

        assert module.VALUE == 42
        assert sentinel.RUNS == [1] and touched == ["read", "read", "compile"]
        assert module.VALUE == 42
        assert sentinel.RUNS == [1] and touched == ["read", "read", "compile"]

    def test_factory_wraps_a_loader_class_for_a_finder(
        self, tmp_path: pathlib.Path, sentinel: Any
    ) -> None:
        write_module(tmp_path, "lazy_found", "import lazy_sentinel\nlazy_sentinel.RUNS.append(2)\n")
        loader_class: Any = SourceFileLoader
        lazy_factory: Any = importlib.util.LazyLoader.factory(loader_class)
        finder = FileFinder(str(tmp_path), (lazy_factory, [".py"]))

        spec = finder.find_spec("lazy_found")

        assert spec is not None and isinstance(spec.loader, importlib.util.LazyLoader)
        module = importlib.util.module_from_spec(spec)
        sys.modules["lazy_found"] = module
        spec.loader.exec_module(module)
        assert sentinel.RUNS == []
        assert module.__name__ == "lazy_found"
        assert sentinel.RUNS == [2]

    def test_a_loader_without_exec_module_is_rejected(self) -> None:
        not_a_loader: Any = object()
        with pytest.raises(TypeError):
            importlib.util.LazyLoader(not_a_loader)


class TestReloadRunsOneBody:
    """`reload()` | O(p·s + n + m): the module's body again, not the bodies
    of the modules it imports."""

    def test_the_dependency_is_not_re_executed(self, tmp_path: pathlib.Path) -> None:
        counter = 'RUNS = globals().get("RUNS", 0) + 1\n'
        write_module(tmp_path, "reload_dep", counter)
        write_module(tmp_path, "reload_top", "import reload_dep\n" + counter)
        sys.path.insert(0, str(tmp_path))
        top = importlib.import_module("reload_top")
        dep = importlib.import_module("reload_dep")
        assert (top.RUNS, dep.RUNS) == (1, 1)

        assert importlib.reload(top) is top

        assert (top.RUNS, dep.RUNS) == (2, 1)
        assert importlib.reload(top) is top
        assert (top.RUNS, dep.RUNS) == (3, 1)

    def test_reload_finds_the_spec_again(self, tmp_path: pathlib.Path) -> None:
        write_module(tmp_path, "reload_found", "")
        sys.path.insert(0, str(tmp_path))
        module = importlib.import_module("reload_found")
        finder = CountingFinder()
        sys.meta_path.insert(0, finder)

        importlib.reload(module)

        assert finder.calls == ["reload_found"]
        with pytest.raises(ImportError):
            importlib.reload(types.ModuleType("never_imported"))


class TestNamespacePackages:
    """`NamespaceLoader` | `__path__` is recomputed when `sys.path` changes."""

    def test_the_path_gains_a_portion_when_sys_path_does(self, tmp_path: pathlib.Path) -> None:
        for portion in ("one", "two"):
            (tmp_path / portion / "ns_probe").mkdir(parents=True)
        write_module(tmp_path / "two" / "ns_probe", "b", "")
        sys.path.insert(0, str(tmp_path / "one"))
        package = importlib.import_module("ns_probe")
        assert list(package.__path__) == [str(tmp_path / "one" / "ns_probe")]
        assert type(package.__loader__).__name__.endswith("NamespaceLoader")

        sys.path.insert(0, str(tmp_path / "two"))

        assert list(package.__path__) == [
            str(tmp_path / "two" / "ns_probe"),
            str(tmp_path / "one" / "ns_probe"),
        ]
        assert importlib.import_module("ns_probe.b").__file__ == str(
            tmp_path / "two" / "ns_probe" / "b.py"
        )

    def test_a_regular_module_on_a_later_entry_wins(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "one" / "shadow_ns").mkdir(parents=True)
        (tmp_path / "two").mkdir()
        write_module(tmp_path / "two", "shadow_ns", "KIND = 'module'\n")
        sys.path[:0] = [str(tmp_path / "one"), str(tmp_path / "two")]

        module = importlib.import_module("shadow_ns")

        assert module.KIND == "module" and not hasattr(module, "__path__")

    def test_the_loader_methods(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "ns_loader").mkdir()
        sys.path.insert(0, str(tmp_path))
        package = importlib.import_module("ns_loader")
        loader: Any = package.__loader__

        assert loader.get_source("ns_loader") == ""
        assert isinstance(loader.get_code("ns_loader"), types.CodeType)
        assert loader.is_package("ns_loader") is True
        assert loader.create_module(package.__spec__) is None
        assert loader.exec_module(package) is None


class TestLoaderAbcs:
    """`importlib.abc` rows: `get_code()` compiles per call at the
    `InspectLoader` level, `SourceLoader.get_code()` drives the subclass's
    methods in a fixed order, and the defaults do what the rows say."""

    def test_inspect_loader_get_code_compiles_on_every_call(self) -> None:
        calls: list[str] = []

        class Loader(importlib.abc.InspectLoader):
            def get_source(self, fullname: str) -> str | None:
                calls.append(fullname)
                return None if fullname == "empty" else "X = 1\n"

            @staticmethod
            def source_to_code(data: Any, path: Any = "<string>") -> Any:
                calls.append("compile")
                return importlib.abc.InspectLoader.source_to_code(data, path)

        loader = Loader()
        first, second = loader.get_code("mod"), loader.get_code("mod")

        assert isinstance(first, types.CodeType) and first is not second
        assert first.co_filename == "<string>"
        assert loader.get_code("empty") is None
        assert calls == ["mod", "compile", "mod", "compile", "empty"]
        with pytest.raises(ImportError):
            loader.is_package("mod")

    def test_execution_loader_get_code_stamps_the_filename(self) -> None:
        class Loader(importlib.abc.ExecutionLoader):
            def get_source(self, fullname: str) -> str:
                return "X = 1\n"

            def get_filename(self, fullname: str) -> str:
                return f"/virtual/{fullname}.py"

        code = Loader().get_code("mod")
        assert code is not None and code.co_filename == "/virtual/mod.py"

    def test_source_loader_get_code_drives_the_subclass_methods(self) -> None:
        class Loader(importlib.abc.SourceLoader):
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []
                self.written: dict[str, bytes] = {}
                self.source = b"X = 1\n"
                self.path = "/virtual/mod.py"

            def get_filename(self, fullname: str) -> str:
                return self.path

            def get_data(self, path: str) -> bytes:
                self.calls.append(("get_data", path))
                if path == self.path:
                    return self.source
                if path in self.written:
                    return self.written[path]
                raise OSError(path)

            def path_stats(self, path: str) -> dict[str, Any]:
                self.calls.append(("path_stats", path))
                return {"mtime": 1_000, "size": len(self.source)}

            def set_data(self, path: str, data: bytes) -> None:
                self.calls.append(("set_data", path))
                self.written[path] = data

            def source_to_code(self, data: Any, path: Any, *args: Any, **kwargs: Any) -> Any:
                self.calls.append(("source_to_code", str(path)))
                return super().source_to_code(data, path, *args, **kwargs)

        loader = Loader()
        cache = importlib.util.cache_from_source(loader.path)

        code = loader.get_code("mod")

        assert isinstance(code, types.CodeType)
        assert loader.calls == [
            ("path_stats", loader.path),
            ("get_data", cache),
            ("get_data", loader.path),
            ("source_to_code", loader.path),
            ("set_data", cache),
        ]
        assert loader.written[cache][:4] == importlib.util.MAGIC_NUMBER

        loader.calls.clear()
        assert isinstance(loader.get_code("mod"), types.CodeType)
        assert loader.calls == [("path_stats", loader.path), ("get_data", cache)]
        assert loader.get_source("mod") == "X = 1\n"
        assert loader.is_package("mod") is False

    def test_the_defaults(self) -> None:
        class Finder(importlib.abc.MetaPathFinder):
            pass

        class EntryFinder(importlib.abc.PathEntryFinder):
            pass

        class Loader(importlib.abc.Loader):
            pass

        class Source(importlib.abc.SourceLoader):
            def get_filename(self, fullname: str) -> str:
                return "/virtual/x.py"

            def get_data(self, path: str) -> bytes:
                return b""

        assert Finder().invalidate_caches() is None
        assert EntryFinder().invalidate_caches() is None
        assert Loader().create_module(ModuleSpec("x", None)) is None
        with pytest.raises(ImportError):
            Loader().load_module("x")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(OSError):
                Source().path_mtime("/virtual/x.py")
        with pytest.raises(OSError):
            Source().path_stats("/virtual/x.py")
        assert Source().set_data("/virtual/x.pyc", b"") is None
        assert isinstance(importlib.abc.InspectLoader.source_to_code("X = 1\n"), types.CodeType)

    def test_the_machinery_classes_are_registered(self, tmp_path: pathlib.Path) -> None:
        assert issubclass(importlib.machinery.PathFinder, importlib.abc.MetaPathFinder)
        assert issubclass(FileFinder, importlib.abc.PathEntryFinder)
        assert isinstance(FileFinder(str(tmp_path)), importlib.abc.PathEntryFinder)
        assert issubclass(SourceFileLoader, importlib.abc.SourceLoader)
        assert issubclass(SourceFileLoader, importlib.abc.FileLoader)
        assert issubclass(importlib.machinery.ExtensionFileLoader, importlib.abc.ExecutionLoader)
        assert issubclass(importlib.machinery.SourcelessFileLoader, importlib.abc.FileLoader)

    def test_load_module_is_a_deprecated_shim_that_runs_the_body(
        self, tmp_path: pathlib.Path
    ) -> None:
        write_module(tmp_path, "shimmed", "VALUE = 7\n")
        loader = SourceFileLoader("shimmed", str(tmp_path / "shimmed.py"))

        with pytest.warns(DeprecationWarning):
            module = loader.load_module("shimmed")

        assert sys.modules["shimmed"] is module and module.VALUE == 7
        assert loader.get_filename("shimmed") == str(tmp_path / "shimmed.py")
        assert loader.name == "shimmed" and loader.path == str(tmp_path / "shimmed.py")
        assert loader.get_data(str(tmp_path / "shimmed.py")) == b"VALUE = 7\n"
        assert loader.path_stats(str(tmp_path / "shimmed.py"))["size"] == 10
        spec = module.__spec__
        assert spec is not None and loader.create_module(spec) is None
        assert isinstance(loader.source_to_code(b"X = 1\n", "x.py"), types.CodeType)

    def test_sourceless_loader_reads_bytecode_only(self, tmp_path: pathlib.Path) -> None:
        source = write_module(tmp_path, "compiled_only", "VALUE = 3\n")
        pyc = tmp_path / "compiled_only.pyc"
        py_compile.compile(str(source), cfile=str(pyc), doraise=True)
        source.unlink()
        loader = importlib.machinery.SourcelessFileLoader("compiled_only", str(pyc))

        code = loader.get_code("compiled_only")

        assert isinstance(code, types.CodeType)
        assert loader.get_source("compiled_only") is None
        assert loader.name == "compiled_only" and loader.path == str(pyc)

    def test_extension_loader_finder_side_methods_load_nothing(self) -> None:
        dynload = pathlib.Path(sysconfig.get_paths()["stdlib"]) / "lib-dynload"
        suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
        candidates = (
            sorted(path for path in dynload.glob("*") if path.name.endswith(suffixes))
            if dynload.is_dir()
            else []
        )
        if not candidates:
            pytest.skip("no extension module in lib-dynload")
        path = candidates[0]
        name = path.name.split(".")[0]
        loader = importlib.machinery.ExtensionFileLoader(name, str(path))

        assert loader.get_code(name) is None
        assert loader.get_source(name) is None
        assert loader.is_package(name) is False
        assert loader.get_filename(name) == str(path)
        assert loader.name == name and loader.path == str(path)

    def test_builtin_and_frozen_importers_find_their_own(self) -> None:
        spec = importlib.machinery.BuiltinImporter.find_spec("sys")
        assert spec is not None and spec.origin == "built-in"
        assert spec.loader is importlib.machinery.BuiltinImporter
        assert importlib.machinery.BuiltinImporter.find_spec("json") is None

        frozen = next(
            name
            for name, module in list(sys.modules.items())
            if getattr(getattr(module, "__spec__", None), "loader", None)
            is importlib.machinery.FrozenImporter
        )
        spec = importlib.machinery.FrozenImporter.find_spec(frozen)
        assert spec is not None and spec.origin == "frozen"
        assert importlib.machinery.FrozenImporter.find_spec("json") is None

    def test_suffix_lists(self) -> None:
        machinery = importlib.machinery
        assert machinery.all_suffixes() == (
            machinery.SOURCE_SUFFIXES + machinery.BYTECODE_SUFFIXES + machinery.EXTENSION_SUFFIXES
        )
        assert machinery.all_suffixes() is not machinery.all_suffixes()
        assert ".py" in machinery.SOURCE_SUFFIXES and ".pyc" in machinery.BYTECODE_SUFFIXES

    def test_file_finder_path_hook_needs_a_directory(self, tmp_path: pathlib.Path) -> None:
        hook = FileFinder.path_hook((SourceFileLoader, [".py"]))
        finder = hook(str(tmp_path))
        assert isinstance(finder, FileFinder) and finder.path == str(tmp_path)
        with pytest.raises(ImportError):
            hook(str(tmp_path / "absent"))

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only finder")
    def test_windows_registry_finder(self) -> None:
        assert (
            importlib.machinery.WindowsRegistryFinder.find_spec("no_such_module_anywhere") is None
        )


class TestResources:
    """`files()` | O(1) on a file-system package, O(z) on a zip archive per
    call, O(D) with no anchor; `as_file()` copies only what has no path."""

    def test_files_on_a_package_is_its_directory(self, tmp_path: pathlib.Path) -> None:
        import json

        root = importlib.resources.files("json")
        assert isinstance(root, pathlib.Path)
        assert root == pathlib.Path(json.__file__).parent
        assert importlib.resources.files(json) == root

        (tmp_path / "res_pkg").mkdir()
        write_module(tmp_path / "res_pkg", "__init__", 'RUNS = globals().get("RUNS", 0) + 1\n')
        (tmp_path / "res_pkg" / "data.txt").write_text("payload", encoding="utf-8")
        sys.path.insert(0, str(tmp_path))
        resource = importlib.resources.files("res_pkg").joinpath("data.txt")
        importlib.resources.files("res_pkg")
        assert sys.modules["res_pkg"].RUNS == 1
        assert resource.read_text(encoding="utf-8") == "payload"
        assert resource.read_bytes() == b"payload"
        assert resource.is_file() and not resource.is_dir() and resource.name == "data.txt"
        with resource.open("rb") as handle:
            assert handle.read() == b"payload"
        assert {child.name for child in importlib.resources.files("res_pkg").iterdir()} >= {
            "data.txt",
            "__init__.py",
        }

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="files() requires an anchor before 3.12")
    def test_no_anchor_costs_the_call_stack_depth(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "stack_probe").mkdir()
        write_module(
            tmp_path / "stack_probe",
            "__init__",
            "import importlib.resources\n\n"
            "def deep(n):\n"
            "    return importlib.resources.files() if n == 0 else deep(n - 1)\n\n"
            "def deep_anchored(n):\n"
            "    return importlib.resources.files(__name__) if n == 0 else deep_anchored(n - 1)\n",
        )
        sys.path.insert(0, str(tmp_path))
        probe = importlib.import_module("stack_probe")
        limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(limit, 5_000))
        try:
            assert probe.deep(0) == probe.deep_anchored(0) == tmp_path / "stack_probe"
            shallow = best_ns(lambda: probe.deep(50), 3) - best_ns(
                lambda: probe.deep_anchored(50), 3
            )
            deep = best_ns(lambda: probe.deep(1_500), 3) - best_ns(
                lambda: probe.deep_anchored(1_500), 3
            )
        finally:
            sys.setrecursionlimit(limit)

        ratio = deep / shallow
        assert 6 < ratio < 600, f"30x the stack depth cost {ratio:.1f}x beyond the recursion itself"

    @staticmethod
    def _zipped_package(directory: pathlib.Path, name: str, entries: int) -> types.ModuleType:
        archive = directory / f"{name}.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr(f"{name}/__init__.py", "")
            zipped.writestr(f"{name}/data.txt", "zipped")
            for index in range(entries):
                zipped.writestr(f"{name}/filler/f{index}.txt", "x")
        sys.path.insert(0, str(archive))
        return importlib.import_module(name)

    def test_files_on_a_zip_reads_the_archive_per_call_and_joinpath_does_not(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = self._zipped_package(tmp_path, "zipped_pkg", 5)
        reads: list[int] = []
        zip_file: Any = zipfile.ZipFile
        original = zip_file._RealGetContents
        monkeypatch.setattr(
            zip_file, "_RealGetContents", lambda self: reads.append(1) or original(self)
        )

        root = importlib.resources.files(module)
        importlib.resources.files(module)
        assert len(reads) == 2

        assert root.joinpath("data.txt").read_text(encoding="utf-8") == "zipped"
        assert root.joinpath("data.txt").is_file()
        assert len(reads) == 2

    @pytest.mark.timing
    def test_files_on_a_zip_follows_the_archive_size(self, tmp_path: pathlib.Path) -> None:
        files_cost: dict[int, float] = {}
        join_cost: dict[int, float] = {}
        list_cost: dict[int, float] = {}
        for entries in (10, 3_000):
            module = self._zipped_package(tmp_path, f"zip{entries}", entries)
            files_cost[entries] = best_ns(lambda module=module: importlib.resources.files(module))
            root = importlib.resources.files(module)
            join_cost[entries] = best_ns(lambda root=root: root.joinpath("data.txt"))
            list_cost[entries] = best_ns(lambda root=root: list(root.iterdir()))

        files_ratio = files_cost[3_000] / files_cost[10]
        join_ratio = join_cost[3_000] / join_cost[10]
        list_ratio = list_cost[3_000] / list_cost[10]
        assert 15 < files_ratio < 30_000, (
            f"300x the archive entries cost files() {files_ratio:.1f}x"
        )
        assert join_ratio < 4, f"300x the archive entries cost joinpath() {join_ratio:.1f}x"
        assert 15 < list_ratio < 30_000, (
            f"300x the archive entries cost iterdir() {list_ratio:.1f}x"
        )

    def test_as_file_yields_a_path_unchanged_and_copies_a_zip_resource(
        self, tmp_path: pathlib.Path
    ) -> None:
        resource = importlib.resources.files("json").joinpath("decoder.py")
        with importlib.resources.as_file(resource) as path:
            assert path is resource

        module = self._zipped_package(tmp_path, "as_file_pkg", 2)
        zipped = importlib.resources.files(module).joinpath("data.txt")
        assert not isinstance(zipped, pathlib.Path)
        with importlib.resources.as_file(zipped) as path:
            assert isinstance(path, pathlib.Path) and path.exists()
            assert path.read_bytes() == zipped.read_bytes() == b"zipped"
        assert not path.exists()

    def test_functional_api_matches_files(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "func_pkg").mkdir()
        write_module(tmp_path / "func_pkg", "__init__", "")
        (tmp_path / "func_pkg" / "data.txt").write_text("payload", encoding="utf-8")
        sys.path.insert(0, str(tmp_path))
        resources = importlib.resources
        resolved: list[Any] = []
        if sys.version_info >= (3, 11):
            common: Any = importlib.import_module("importlib.resources._common")
            functional: Any = sys.modules[resources.read_text.__module__]
            files = common.files

            def counting(anchor: Any) -> Any:
                resolved.append(anchor)
                return files(anchor)

            monkeypatch.setattr(common, "files", counting)
            if functional is not common and hasattr(functional, "files"):
                monkeypatch.setattr(functional, "files", counting)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert resources.read_text("func_pkg", "data.txt", encoding="utf-8") == "payload"
            assert resources.read_text("func_pkg", "data.txt", encoding="utf-8") == "payload"
            if sys.version_info >= (3, 11):
                assert resolved == ["func_pkg", "func_pkg"]
            assert resources.read_binary("func_pkg", "data.txt") == b"payload"
            with resources.open_text("func_pkg", "data.txt", encoding="utf-8") as text:
                assert text.read() == "payload"
            with resources.open_binary("func_pkg", "data.txt") as binary:
                assert binary.read() == b"payload"
            with resources.path("func_pkg", "data.txt") as path:
                assert path == tmp_path / "func_pkg" / "data.txt"
            assert resources.is_resource("func_pkg", "data.txt")
            assert not resources.is_resource("func_pkg", "absent.txt")
        if (3, 11) <= sys.version_info < (3, 12, 10) or sys.version_info >= (3, 13):
            with pytest.warns(DeprecationWarning):
                contents = resources.contents("func_pkg")
        else:
            contents = resources.contents("func_pkg")
        assert isinstance(contents, list) is (sys.version_info < (3, 13))
        assert isinstance(contents, Iterator) is (sys.version_info >= (3, 13))
        assert set(contents) >= {"data.txt", "__init__.py"}
        assert hasattr(resources, "Package")
        assert hasattr(resources, "Anchor") is (sys.version_info >= (3, 12))

    def test_traversable_resources_defaults_go_through_files(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "data.txt").write_bytes(b"payload")

        class Reader(resources_abc.TraversableResources):
            def files(self) -> pathlib.Path:
                return tmp_path

        reader = Reader()
        with reader.open_resource("data.txt") as handle:
            assert handle.read() == b"payload"
        assert reader.is_resource("data.txt") and not reader.is_resource("absent.txt")
        assert set(reader.contents()) == {"data.txt"}
        with pytest.raises(FileNotFoundError):
            reader.resource_path("data.txt")
        assert isinstance(reader, resources_abc.ResourceReader)


class TestNamespacePackageResources:
    """`Traversable.joinpath()` | O(k log k) per segment on a `MultiplexedPath`,
    and the protocol default's one `iterdir()` per directory a segment passes."""

    @staticmethod
    def _namespace(tmp_path: pathlib.Path, name: str, children: int) -> Any:
        for portion in ("one", "two"):
            (tmp_path / name / portion / name).mkdir(parents=True)
        for index in range(children):
            (tmp_path / name / "one" / name / f"f{index}.txt").write_bytes(b"x")
        (tmp_path / name / "two" / name / "target.txt").write_bytes(b"target")
        sys.path[:0] = [str(tmp_path / name / "one"), str(tmp_path / name / "two")]
        return importlib.resources.files(name)

    def test_iterdir_merges_the_portions(self, tmp_path: pathlib.Path) -> None:
        root = self._namespace(tmp_path, "merged_ns", 2)

        assert type(root).__name__ == "MultiplexedPath"
        names = [child.name for child in root.iterdir()]
        assert set(names) == {"f0.txt", "f1.txt", "target.txt"}
        (tmp_path / "merged_ns" / "two" / "merged_ns" / "a_last_portion.txt").write_bytes(b"")
        (tmp_path / "merged_ns" / "two" / "merged_ns" / "f0.txt").write_bytes(b"shadowed")
        names = [child.name for child in root.iterdir()]
        assert names.count("f0.txt") == 1
        assert root.joinpath("f0.txt").read_bytes() == b"x"
        if sys.version_info >= (3, 12):
            assert names == sorted(names)
        else:
            assert set(names[:2]) == {"f0.txt", "f1.txt"}
            assert set(names[2:]) == {"target.txt", "a_last_portion.txt"}
        assert root.joinpath("target.txt").read_bytes() == b"target"
        assert root.is_dir() and not root.is_file()

    @pytest.mark.timing
    def test_joinpath_follows_the_children_across_portions(self, tmp_path: pathlib.Path) -> None:
        costs: dict[int, float] = {}
        for children in (10, 2_000):
            root = self._namespace(tmp_path, f"ns{children}", children)
            costs[children] = best_ns(lambda root=root: root.joinpath("target.txt"))

        ratio = costs[2_000] / costs[10]
        assert 20 < ratio < 4_000, f"200x the children cost joinpath() {ratio:.1f}x"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the default joinpath() arrived in 3.12")
    def test_the_default_joinpath_lists_once_per_directory_passed(self) -> None:
        class Node(resources_abc.Traversable):
            def __init__(self, name: str, children: list[Node] | None = None) -> None:
                self._name = name
                self.children = children or []
                self.listed = 0

            def iterdir(self) -> Iterator[Node]:
                self.listed += 1
                return iter(self.children)

            def is_dir(self) -> bool:
                return bool(self.children)

            def is_file(self) -> bool:
                return not self.children

            def open(self, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
                raise NotImplementedError

            @property
            def name(self) -> str:
                return self._name

        leaf = Node("leaf")
        middle = Node("middle", [Node("other"), leaf])
        root = Node("root", [Node("decoy"), middle])

        assert root.joinpath("middle/leaf") is leaf
        assert (root.listed, middle.listed, leaf.listed) == (1, 1, 0)
        assert root.joinpath("middle", "leaf") is leaf
        assert (root.listed, middle.listed) == (2, 2)
        assert root.joinpath() is root
        with pytest.raises(resources_abc.TraversalError):
            root.joinpath("absent")


class TestMetadataLookups:
    """`distribution()` | O(p) with no file read; `version()` and the
    `Distribution` properties parse `METADATA` on every access;
    `distributions()` lists each path entry once per mtime."""

    @pytest.fixture
    def reads(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []
        original = importlib.metadata.PathDistribution.read_text

        def counting(self: Any, filename: Any) -> Any:
            calls.append(str(filename))
            return original(self, filename)

        monkeypatch.setattr(importlib.metadata.PathDistribution, "read_text", counting)
        return calls

    @pytest.fixture
    def site(self, tmp_path: pathlib.Path) -> pathlib.Path:
        site = tmp_path / "site"
        site.mkdir()
        make_dist(site, "alpha", version="1.2", extra_metadata="Requires-Dist: beta>=1\n")
        sys.path.insert(0, str(site))
        return site

    def test_finding_reads_no_file_and_each_property_reads_the_metadata(
        self, site: pathlib.Path, reads: list[str]
    ) -> None:
        dist = importlib.metadata.distribution("alpha")
        assert isinstance(dist, importlib.metadata.PathDistribution)
        assert reads == []

        assert importlib.metadata.version("alpha") == "1.2"
        assert importlib.metadata.version("alpha") == "1.2"
        assert reads == ["METADATA", "METADATA"]

        reads.clear()
        assert dist.version == "1.2" and dist.name == "alpha"
        assert reads == ["METADATA", "METADATA"]
        assert dist.requires == ["beta>=1"]
        assert importlib.metadata.requires("alpha") == ["beta>=1"]
        assert importlib.metadata.metadata("alpha")["Version"] == "1.2"

    def test_a_missing_distribution_raises_with_its_name(self, site: pathlib.Path) -> None:
        with pytest.raises(importlib.metadata.PackageNotFoundError) as info:
            importlib.metadata.distribution("not-installed")
        assert info.value.name == "not-installed"
        with pytest.raises(importlib.metadata.PackageNotFoundError):
            importlib.metadata.version("not-installed")

    def test_at_wraps_a_path_without_reading(self, site: pathlib.Path, reads: list[str]) -> None:
        dist = importlib.metadata.Distribution.at(site / "alpha-1.2.dist-info")
        assert reads == []
        assert dist.locate_file("x.py") == site / "x.py"
        assert dist.read_text("absent.txt") is None
        assert dist.version == "1.2"

    def test_distributions_is_lazy_and_lists_each_entry_once(
        self, site: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listed: list[str] = []
        original = os.listdir

        def counting(path: Any = ".") -> Any:
            listed.append(str(path))
            return original(path)

        monkeypatch.setattr(os, "listdir", counting)
        metadata_path_finder().invalidate_caches()
        stat_before = os.stat(site)

        found = importlib.metadata.distributions()
        assert listed == []

        names = [dist.metadata["Name"] for dist in found]
        assert "alpha" in names
        assert listed.count(str(site)) == 1

        assert "alpha" in [dist.metadata["Name"] for dist in importlib.metadata.distributions()]
        assert listed.count(str(site)) == 1

        if sys.version_info >= (3, 11):
            importlib.invalidate_caches()
        else:
            metadata_path_finder().invalidate_caches()
        list(importlib.metadata.distributions())
        assert listed.count(str(site)) == 2

        make_dist(site, "arrived")
        assert os.stat(site).st_mtime_ns != stat_before.st_mtime_ns
        assert importlib.metadata.version("arrived") == "1.0"
        assert listed.count(str(site)) == 3

    def test_finders_and_contexts(self, site: pathlib.Path) -> None:
        context = importlib.metadata.DistributionFinder.Context()
        assert context.path is sys.path and context.name is None
        assert (
            importlib.metadata.DistributionFinder.Context(name="alpha", path=[str(site)]).name
            == "alpha"
        )

        found = list(
            importlib.metadata.MetadataPathFinder.find_distributions(
                importlib.metadata.DistributionFinder.Context(path=[str(site)])
            )
        )
        assert [dist.metadata["Name"] for dist in found] == ["alpha"]
        via_machinery = list(
            importlib.machinery.PathFinder.find_distributions(
                importlib.metadata.DistributionFinder.Context(name="alpha", path=[str(site)])
            )
        )
        assert [dist.version for dist in via_machinery] == ["1.2"]
        assert [
            d.version
            for d in importlib.metadata.Distribution.discover(name="alpha", path=[str(site)])
        ] == ["1.2"]


class TestEntryPointsReadEveryDistribution:
    """`entry_points()` | O(p + d + E): one `entry_points.txt` read per
    distribution whatever the selection, then linear scans on the tuple."""

    @staticmethod
    def _site(tmp_path: pathlib.Path, count: int) -> pathlib.Path:
        site = tmp_path / f"site{count}"
        site.mkdir()
        for index in range(count):
            make_dist(
                site,
                f"plug{count}x{index}",
                entry_points=f"[demo.group{index % 5}]\nep{index} = plugin{count}x{index}:register\n",
            )
            write_module(site, f"plugin{count}x{index}", "def register():\n    return __name__\n")
        return site

    def test_one_read_per_distribution_whatever_the_group(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reads: list[str] = []
        original = importlib.metadata.PathDistribution.read_text
        monkeypatch.setattr(
            importlib.metadata.PathDistribution,
            "read_text",
            lambda self, filename: reads.append(str(filename)) or original(self, filename),
        )
        counts: dict[int, int] = {}
        for count in (5, 50):
            site = self._site(tmp_path, count)
            sys.path.insert(0, str(site))
            reads.clear()
            found = importlib.metadata.entry_points(group="demo.group0")
            counts[count] = reads.count("entry_points.txt")
            assert set(reads) == {"entry_points.txt"}
            assert len(found) >= count // 5
            sys.path.remove(str(site))

        assert counts[50] - counts[5] == 45, counts

    def test_the_tuple_and_its_entries(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        site = self._site(tmp_path, 5)
        sys.path.insert(0, str(site))

        found = importlib.metadata.entry_points(group="demo.group1")
        assert isinstance(found, importlib.metadata.EntryPoints)
        assert isinstance(found, tuple if sys.version_info >= (3, 12) else list)
        entry = found["ep1"]
        assert entry.name == "ep1" and entry.group == "demo.group1"
        assert entry.value == "plugin5x1:register"
        assert entry.module == "plugin5x1" and entry.attr == "register" and entry.extras == []
        assert entry.matches(group="demo.group1", name="ep1") and not entry.matches(name="ep2")
        assert entry.dist is not None and entry.dist.metadata["Name"] == "plug5x1"
        assert entry.load()() == "plugin5x1"
        assert tuple(found.select(name="ep1")) == (entry,)
        assert found.names >= {"ep1"} and found.groups == {"demo.group1"}
        with pytest.raises(KeyError):
            found["absent"]
        if sys.version_info >= (3, 12):
            with pytest.raises(KeyError):
                found[0]  # type: ignore[call-overload]
        else:
            with pytest.warns(DeprecationWarning):
                assert found[0] == entry  # type: ignore[call-overload]
        dist = importlib.metadata.distribution("plug5x1")
        assert tuple(dist.entry_points) == (entry,)
        reads: list[str] = []
        read_text = importlib.metadata.PathDistribution.read_text
        monkeypatch.setattr(
            importlib.metadata.PathDistribution,
            "read_text",
            lambda self, filename: reads.append(str(filename)) or read_text(self, filename),
        )
        assert tuple(dist.entry_points) == tuple(dist.entry_points) == (entry,)
        assert reads == ["entry_points.txt", "entry_points.txt"]

        spelled = importlib.metadata.EntryPoint("n", "pkg.mod:obj.attr [x, y]", "g")
        assert (
            spelled.module == "pkg.mod"
            and spelled.attr == "obj.attr"
            and spelled.extras == ["x", "y"]
        )
        assert importlib.metadata.EntryPoint.pattern.match(spelled.value) is not None

    @pytest.mark.timing
    def test_select_and_indexing_are_linear(self) -> None:
        costs: dict[int, tuple[float, float, float]] = {}
        for size in (100, 20_000):
            points = importlib.metadata.EntryPoints(
                importlib.metadata.EntryPoint(f"ep{i}", f"m{i}:f", f"g{i % 10}")
                for i in range(size)
            )
            costs[size] = (
                best_ns(lambda points=points: points["ep0"]),
                best_ns(lambda points=points: points.select(group="g3")),
                best_ns(lambda points=points: points.names),
            )

        for label, small, large in zip(
            ("[name]", "select()", "names"), costs[100], costs[20_000], strict=True
        ):
            ratio = large / small
            assert 40 < ratio < 4_000, f"200x the entry points cost {label} {ratio:.1f}x"


class TestDistributionFiles:
    """`Distribution.files` | O(F): `RECORD` with a `stat()` per file from
    3.12; `packages_distributions()` prefers `top_level.txt`."""

    def test_files_are_stat_checked_from_312(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        site = tmp_path / "site"
        site.mkdir()
        info = make_dist(site, "recorded", record="recorded/__init__.py,,\nrecorded/gone.py,,\n")
        (site / "recorded").mkdir()
        write_module(site / "recorded", "__init__", "")
        checked: list[str] = []
        original = pathlib.Path.exists
        monkeypatch.setattr(
            pathlib.Path,
            "exists",
            lambda self, **kw: checked.append(self.name) or original(self, **kw),
        )

        files = importlib.metadata.Distribution.at(info).files

        assert files is not None
        if sys.version_info >= (3, 12):
            assert [str(path) for path in files] == ["recorded/__init__.py"]
            assert checked == ["__init__.py", "gone.py"]
        else:
            assert [str(path) for path in files] == ["recorded/__init__.py", "recorded/gone.py"]
        assert files[0].locate() == site / "recorded" / "__init__.py"
        assert files[0].read_text() == "" and files[0].read_binary() == b""
        assert files[0].dist.metadata["Name"] == "recorded" and files[0].size is None
        sys.path.insert(0, str(site))
        assert importlib.metadata.files("recorded") == files
        reads: list[str] = []
        read_text = importlib.metadata.PathDistribution.read_text
        monkeypatch.setattr(
            importlib.metadata.PathDistribution,
            "read_text",
            lambda self, filename: reads.append(str(filename)) or read_text(self, filename),
        )
        dist = importlib.metadata.Distribution.at(info)
        assert dist.files == dist.files == files
        assert reads == ["RECORD", "RECORD"]

    def test_packages_distributions_reads_top_level_before_record(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        site = tmp_path / "site"
        site.mkdir()
        make_dist(
            site, "declared", top_level="declared_pkg\n", record="declared_pkg/__init__.py,,\n"
        )
        make_dist(site, "inferred", record="inferred_pkg/__init__.py,,\n")
        for package in ("declared_pkg", "inferred_pkg"):
            (site / package).mkdir()
            write_module(site / package, "__init__", "")
        reads: list[tuple[str, str]] = []
        original = importlib.metadata.PathDistribution.read_text
        monkeypatch.setattr(
            importlib.metadata.PathDistribution,
            "read_text",
            lambda self, filename: (
                reads.append((self._path.name, str(filename))) or original(self, filename)
            ),
        )
        sys.path.insert(0, str(site))

        mapping = importlib.metadata.packages_distributions()

        assert mapping["declared_pkg"] == ["declared"]
        assert ("declared-1.0.dist-info", "top_level.txt") in reads
        assert ("declared-1.0.dist-info", "RECORD") not in reads
        if sys.version_info >= (3, 11):
            assert mapping["inferred_pkg"] == ["inferred"]
            assert ("inferred-1.0.dist-info", "RECORD") in reads
        else:
            assert "inferred_pkg" not in mapping
            assert ("inferred-1.0.dist-info", "RECORD") not in reads


class TestPackageMetadataScans:
    """`metadata[key]` | O(h) and `PackageMetadata.json` | O(h²)."""

    @staticmethod
    def _metadata(site: pathlib.Path, headers: int) -> Any:
        classifiers = "".join(f"Classifier: Topic :: c{index}\n" for index in range(headers))
        info = make_dist(site, f"wide{headers}", extra_metadata=classifiers + "Summary: last\n")
        return importlib.metadata.Distribution.at(info).metadata

    def test_the_protocol_members(self, tmp_path: pathlib.Path) -> None:
        meta = self._metadata(tmp_path, 3)

        assert meta["Summary"] == "last" and meta.get("Summary") == "last"
        assert meta.get("Absent") is None and meta.get("Absent", "x") == "x"
        assert meta.get_all("Classifier") == ["Topic :: c0", "Topic :: c1", "Topic :: c2"]
        assert "summary" in meta and "Absent" not in meta
        assert len(meta) == 7 and set(meta) >= {"Name", "Version", "Summary"}
        assert meta.json["classifier"] == ["Topic :: c0", "Topic :: c1", "Topic :: c2"]
        assert meta.json["summary"] == "last"

    @pytest.mark.timing
    def test_one_key_is_linear_and_json_is_quadratic(self, tmp_path: pathlib.Path) -> None:
        item: dict[int, float] = {}
        json_view: dict[int, float] = {}
        for headers in (100, 3_000):
            meta = self._metadata(tmp_path, headers)
            item[headers] = best_ns(lambda meta=meta: meta["Summary"])
            json_view[headers] = best_ns(lambda meta=meta: meta.json, 3)

        item_ratio = item[3_000] / item[100]
        json_ratio = json_view[3_000] / json_view[100]
        assert 5 < item_ratio < 120, f"30x the headers cost metadata[key] {item_ratio:.1f}x"
        assert 200 < json_ratio < 5_000, f"30x the headers cost json {json_ratio:.1f}x"


class TestVersionBoundaries:
    """The page's Version Notes, asserted by presence on the running version."""

    def test_names_removed_in_312(self) -> None:
        before = sys.version_info < (3, 12)
        assert hasattr(importlib, "find_loader") is before
        assert hasattr(importlib.abc, "Finder") is before
        assert hasattr(importlib.util, "set_package") is before
        assert hasattr(importlib.util, "set_loader") is before
        assert hasattr(importlib.util, "module_for_loader") is before
        assert hasattr(importlib.abc.MetaPathFinder, "find_module") is before
        assert hasattr(importlib.abc.PathEntryFinder, "find_loader") is before
        assert hasattr(importlib.util, "_incompatible_extension_module_restrictions") is not before
        if not before:
            util: Any = importlib.util
            restriction = util._incompatible_extension_module_restrictions(disable_check=True)
            assert restriction.override == -1
            with pytest.raises(RuntimeError):
                restriction.__enter__()

    def test_names_added_in_311_and_313_and_removed_in_314(self) -> None:
        try:
            has_resources_abc = importlib.util.find_spec("importlib.resources.abc") is not None
        except ModuleNotFoundError:
            has_resources_abc = False
        assert has_resources_abc is (sys.version_info >= (3, 11))
        assert hasattr(importlib.machinery, "NamespaceLoader") is (sys.version_info >= (3, 11))
        assert hasattr(importlib.abc, "Traversable") is (sys.version_info < (3, 14))
        assert hasattr(importlib.abc, "ResourceReader") is (sys.version_info < (3, 14))
        assert hasattr(importlib.metadata.Distribution, "origin") is (sys.version_info >= (3, 13))
        assert hasattr(importlib.machinery, "AppleFrameworkLoader") is (sys.version_info >= (3, 13))

    def test_entry_points_without_a_selector(self, tmp_path: pathlib.Path) -> None:
        site = tmp_path / "site"
        site.mkdir()
        make_dist(site, "unselected", entry_points="[demo.unselected]\nep = os:getcwd\n")
        sys.path.insert(0, str(site))

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            everything = importlib.metadata.entry_points()

        if sys.version_info >= (3, 12):
            assert isinstance(everything, importlib.metadata.EntryPoints)
            assert "ep" in everything.select(group="demo.unselected").names
        else:
            assert isinstance(everything, dict)
            assert "demo.unselected" in everything

    def test_entry_point_indexing_before_313(self) -> None:
        entry = importlib.metadata.EntryPoint("n", "m:a", "g")
        if sys.version_info >= (3, 13):
            with pytest.raises(TypeError):
                entry[0]  # type: ignore[index]
        elif sys.version_info >= (3, 11):
            with pytest.warns(DeprecationWarning):
                assert entry[0] == "n"  # type: ignore[index]
        else:
            assert entry[0] == "n"  # type: ignore[index]

    def test_files_on_a_plain_module_before_312(self, tmp_path: pathlib.Path) -> None:
        write_module(tmp_path, "plain_anchor", "")
        sys.path.insert(0, str(tmp_path))
        module = importlib.import_module("plain_anchor")
        if sys.version_info >= (3, 12):
            assert importlib.resources.files(module) == tmp_path
        else:
            with pytest.raises(TypeError):
                importlib.resources.files(module)

    def test_the_functional_api_warns_from_311_until_31210(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.resources.is_resource("json", "decoder.py")
        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert bool(deprecated) is ((3, 11) <= sys.version_info < (3, 12, 10))

    def test_several_path_names_from_313(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "nested_pkg" / "sub").mkdir(parents=True)
        write_module(tmp_path / "nested_pkg", "__init__", "")
        (tmp_path / "nested_pkg" / "sub" / "data.txt").write_text("deep", encoding="utf-8")
        sys.path.insert(0, str(tmp_path))
        resources: Any = importlib.resources
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            if sys.version_info >= (3, 13):
                text = resources.read_text("nested_pkg", "sub", "data.txt", encoding="utf-8")
                assert text == "deep"
            else:
                with pytest.raises(TypeError):
                    resources.read_text("nested_pkg", "sub", "data.txt", encoding="utf-8")

    def test_path_mtime_warns_from_314(self) -> None:
        class Source(importlib.abc.SourceLoader):
            def get_filename(self, fullname: str) -> str:
                return "/virtual/x.py"

            def get_data(self, path: str) -> bytes:
                return b""

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(OSError):
                Source().path_mtime("/virtual/x.py")
        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecated) == (1 if sys.version_info >= (3, 14) else 0)

    def test_bytecode_suffix_aliases_warn_from_314(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            debug = importlib.machinery.DEBUG_BYTECODE_SUFFIXES
            optimized = importlib.machinery.OPTIMIZED_BYTECODE_SUFFIXES
        assert debug == optimized == importlib.machinery.BYTECODE_SUFFIXES
        deprecated = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(deprecated) == (2 if sys.version_info >= (3, 14) else 0)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Distribution.origin arrived in 3.13")
    def test_origin_reads_direct_url(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        info = make_dist(tmp_path, "sourced")
        dist: Any = importlib.metadata.Distribution.at(info)
        assert dist.origin is None
        (info / "direct_url.json").write_text('{"url": "file:///src/sourced"}', encoding="utf-8")
        reads: list[str] = []
        read_text = importlib.metadata.PathDistribution.read_text
        monkeypatch.setattr(
            importlib.metadata.PathDistribution,
            "read_text",
            lambda self, filename: reads.append(str(filename)) or read_text(self, filename),
        )
        first: Any = dist.origin
        second: Any = dist.origin
        assert first.url == second.url == "file:///src/sourced"
        assert reads == ["direct_url.json", "direct_url.json"]


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so the modules, path entries
    and finder caches it creates cannot leak, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next(
            (n, s) for n, s in _blocks() if "assert (top.RUNS, dep.RUNS) == (2, 1)" in s
        )
        mutated = source.replace(
            "assert (top.RUNS, dep.RUNS) == (2, 1)",
            "assert dep.RUNS == [1, 1]  # the dependency",
            1,
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
