"""Tests for docs/stdlib/pkgutil.md.

The page prices the module by the directory entries it lists, the search path
entries it consults and the imports it performs. Listing work is settled by
counting `os.listdir` calls and the entries they return, import work by
watching `sys.modules` and counting `importlib.import_module` calls, and
space by traced allocation with the import system's caches warmed first, so
that finders and modules created by the first run are not counted against the
operation.

Measurement scope:

* `iter_modules()` is asserted to call `os.listdir` nowhere until iterated.
  Iterated over a directory holding two modules, a package, a non-package
  subdirectory of 2,000 files and a subdirectory with a dot in its name, it
  lists the directory, the package and the non-package subdirectory once
  each and the dotted one not at all, and `os.listdir` returns 2,006 entries
  for three names yielded. A second scan lists the directory again, and
  neither imports the package it finds. Three searches of 20,000 entries
  each separate w from m: one directory of 20,000 non-module files (w 20,000,
  m 0) and 100 directories of 200 different modules (w 200, m 20,000) each
  peak more than 10x 100 directories of the same 200 modules (w 200, m 200).
  The total entries are held constant while w and m move separately. A name
  in two path directories is yielded once, from the first; a `str` path
  raises `ValueError`.
* `walk_packages()` over a tree with a package holding a module imports the
  package and its parent and not the module; with no path it walks and
  imports a package on a one-entry `sys.path`. Its generator imports and lists
  nothing until iterated. Over the 100-directory searches above it peaks
  more than 10x higher with distinct names than repeated ones, the m term.
  With the tree already imported by a first walk,
  a flat tree of 40 sibling packages of 400 modules peaks under 3x a tree of
  one such package, against 40x the entries; a chain of ten nested packages
  of 400 modules peaks more than 4x a single one, so the listings along the
  descent are held together. `onerror` is asserted to receive a package that
  fails to import, an `ImportError` to be skipped without it, and any other
  exception to propagate.
* `get_importer()` is asserted to call no path hook on a
  `sys.path_importer_cache` hit, to call a counting hook once on a miss and
  cache what it returns, and to return `None` without caching when no hook
  accepts. `iter_importers()` calls `get_importer()` nowhere until iterated,
  then yields the meta path finders and one finder per `sys.path` entry; a
  dotted name imports its parent and yields one finder per `__path__` entry.
* `get_loader()` on an imported module is asserted to return its
  `__loader__` without calling `importlib.util.find_spec`, and on a name that
  is not imported to call it once, as `find_loader()` does; both warn on 3.12
  and 3.13 and are absent from 3.14. `ImpImporter` and `ImpLoader` are
  asserted to list nothing at construction and to warn on 3.10 and 3.11, and
  to be absent from 3.12.
* `extend_path()` is given a path of 50 entries whose `__eq__` counts calls
  and a search path of 20 directories that each hold a portion: it makes 1,000
  comparisons against those 50 entries, one scan per portion, and one
  `get_importer()` call per directory. It returns a new list, leaves its input
  unchanged, and returns a non-list path as the same object.
* `get_data()` is asserted to return the file's bytes, to import the package,
  to return `None` for an unknown top-level package and to raise
  `FileNotFoundError` for a missing resource. Its peak over a 4 MB file is
  over 4 MB, and over a 4 KB file under 1 MB.
* `resolve_name()` makes one `importlib.import_module` call for
  `'os.path:join.__name__'` and three for `'os.path.join.__name__'`, the
  third being the failed attempt that ends the search.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The log factor in O(e log e) is the sort of each directory listing in
  Lib/pkgutil.py; only the entries listed are counted, not the sort.
* The s term of `find_loader()`, `get_loader()` and `get_data()` is the
  search `importlib.util.find_spec()` performs, read from
  Lib/importlib/_bootstrap_external.py. It is not varied here.
* Search bounds take the finder caches as filled, as the page says. A
  `FileFinder`'s first lookup lists its directory into a cache, which is
  import-system work outside these bounds.
* `extend_path()` also reads `<name>.pkg` files line by line; the page
  excludes them from its bound and no test creates one.
* `get_data()` space is measured at two sizes, 4 KB and 4 MB, so the test
  shows the file is held, not that nothing else grows with it.
* Import cost: `walk_packages()` and `get_data()` run each package's
  `__init__.py`, which the caller writes. Packages are empty in every test.
* Zip archives on the path are outside the page's scope and are not measured.
* `ImpImporter` and `ImpLoader` methods beyond construction are not
  measured; they are deprecated and exist only on 3.10 and 3.11.
* Names the audit finds at runtime that the official documentation does not
  list are left off the page: `read_code`, `iter_importer_modules` and
  `iter_zipimport_modules` are undocumented helpers.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import pathlib
import pkgutil
import re
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pkgutil.md"
EXPECTED_BLOCKS = 9


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def drain(iterator: Iterator[Any]) -> None:
    """Consume an iterator without keeping what it yields."""
    for _ in iterator:
        pass


def touch(path: pathlib.Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_package(path: pathlib.Path, modules: int = 0) -> pathlib.Path:
    touch(path / "__init__.py")
    for index in range(modules):
        touch(path / f"m{index}.py")
    return path


class CountingListdir:
    """Wraps os.listdir, recording each directory listed and the entries returned."""

    def __init__(self) -> None:
        self.original = os.listdir
        self.calls: list[str] = []
        self.entries = 0

    def __call__(self, path: Any = ".") -> list[str]:
        names = self.original(path)
        self.calls.append(os.fspath(path))
        self.entries += len(names)
        return names


class CountingStr(str):
    """A path entry whose equality comparisons are counted."""

    compared = 0

    def __eq__(self, other: object) -> bool:
        CountingStr.compared += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


@pytest.fixture
def importable(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[pathlib.Path]:
    """A directory on sys.path; packages created in it are removed from sys.modules after."""
    monkeypatch.syspath_prepend(str(tmp_path))
    before = set(sys.modules)
    yield tmp_path
    for name in set(sys.modules) - before:
        del sys.modules[name]
    importlib.invalidate_caches()


class TestIterModulesListsWholeDirectories:
    """`iter_modules(path)` | O(e log e) | O(w + m).

    Lazy, then each directory is listed in full, and so is every subdirectory
    checked for an `__init__`, package or not. The space is one listing plus
    the names yielded, which a path of many small directories separates from
    the entries listed in total.
    """

    def test_building_the_generator_lists_nothing(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        touch(tmp_path / "alpha.py")
        listdir = CountingListdir()
        monkeypatch.setattr(os, "listdir", listdir)

        modules = pkgutil.iter_modules([str(tmp_path)])

        assert listdir.calls == []
        assert [info.name for info in modules] == ["alpha"]
        assert listdir.calls == [str(tmp_path)]

    def test_each_scan_lists_again_and_imports_nothing(
        self, importable: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        make_package(importable / "scanpkg")
        listdir = CountingListdir()
        monkeypatch.setattr(os, "listdir", listdir)

        first = [info.name for info in pkgutil.iter_modules([str(importable)])]
        second = [info.name for info in pkgutil.iter_modules([str(importable)])]

        assert first == second == ["scanpkg"]
        assert listdir.calls.count(str(importable)) == 2, "nothing is cached between scans"
        assert "scanpkg" not in sys.modules

    def test_a_non_package_subdirectory_is_listed_in_full(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        touch(tmp_path / "alpha.py")
        touch(tmp_path / "beta.py")
        make_package(tmp_path / "gamma")
        data = tmp_path / "data"
        data.mkdir()
        for index in range(2_000):
            (data / f"row{index}.bin").touch()
        touch(tmp_path / "skipped.dir" / "file.txt")
        listdir = CountingListdir()
        monkeypatch.setattr(os, "listdir", listdir)

        names = [info.name for info in pkgutil.iter_modules([str(tmp_path)])]

        assert names == ["alpha", "beta", "gamma"]
        assert sorted(listdir.calls) == sorted(
            [str(tmp_path), str(tmp_path / "data"), str(tmp_path / "gamma")]
        )
        assert listdir.entries == 5 + 2_000 + 1, f"{listdir.entries} entries listed"

    @staticmethod
    def _trees(root: pathlib.Path) -> dict[str, list[str]]:
        """Three searches of 20,000 entries each, split differently between w and m.

        `listing` is one directory of 20,000 non-module files (w 20,000, m 0),
        `repeated` 100 directories of the same 200 modules (w 200, m 200), and
        `distinct` 100 directories of 200 different modules (w 200, m 20,000).
        """
        listing = root / "listing"
        listing.mkdir()
        for index in range(20_000):
            (listing / f"f{index}.txt").touch()
        trees: dict[str, list[str]] = {"listing": [str(listing)], "repeated": [], "distinct": []}
        for directory in range(100):
            for kind in ("repeated", "distinct"):
                path = root / f"{kind}{directory}"
                path.mkdir()
                for index in range(200):
                    stem = f"m{index}" if kind == "repeated" else f"m{directory}_{index}"
                    (path / f"{stem}.py").touch()
                trees[kind].append(str(path))
        for paths in trees.values():
            for path in paths:
                pkgutil.get_importer(path)
        return trees

    def test_the_peak_follows_one_listing_plus_the_names_not_all_entries(
        self, tmp_path: pathlib.Path
    ) -> None:
        trees = self._trees(tmp_path)
        drain(pkgutil.iter_modules(trees["repeated"]))

        peaks = {
            kind: peak_bytes(lambda paths=paths: drain(pkgutil.iter_modules(paths)))
            for kind, paths in trees.items()
        }

        assert peaks["listing"] > peaks["repeated"] * 10, f"the w term is missing: {peaks}"
        assert peaks["distinct"] > peaks["repeated"] * 10, f"the m term is missing: {peaks}"

    def test_the_first_directory_wins_a_duplicate_name(self, tmp_path: pathlib.Path) -> None:
        first, second = tmp_path / "first", tmp_path / "second"
        touch(first / "shared.py")
        touch(second / "shared.py")
        touch(second / "extra.py")

        found = list(pkgutil.iter_modules([str(first), str(second)]))

        assert [info.name for info in found] == ["shared", "extra"]
        assert found[0].module_finder.path == str(first)  # type: ignore[union-attr]

    def test_a_string_path_is_rejected(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(ValueError, match="path must be None or list"):
            list(pkgutil.iter_modules(str(tmp_path)))


class TestModuleInfo:
    """`ModuleInfo` | O(1) | O(1): a named tuple of three fields."""

    def test_it_is_a_three_field_tuple(self, tmp_path: pathlib.Path) -> None:
        make_package(tmp_path / "pkg")

        (info,) = pkgutil.iter_modules([str(tmp_path)])

        assert isinstance(info, tuple)
        assert pkgutil.ModuleInfo._fields == ("module_finder", "name", "ispkg")
        assert info == (info.module_finder, "pkg", True)


class TestWalkPackagesImportsPackages:
    """`walk_packages()` | O(e log e) plus importing p packages | O(d·(w + m)) plus p.

    Every package yielded is imported and stays imported; modules are not.
    With the imports already done, the peak follows the listing and names held
    at each level of the current descent: more sibling packages do not raise
    it, while depth and the names one search yields do.
    """

    def test_packages_are_imported_and_modules_are_not(self, importable: pathlib.Path) -> None:
        top = make_package(importable / "walktop")
        touch(top / "mod.py")
        touch(make_package(top / "sub") / "leaf.py")

        names = [info.name for info in pkgutil.walk_packages([str(top)], "walktop.")]

        assert names == ["walktop.mod", "walktop.sub", "walktop.sub.leaf"]
        assert "walktop.sub" in sys.modules
        assert "walktop" in sys.modules, "importing walktop.sub imports its parent"
        assert "walktop.mod" not in sys.modules
        assert "walktop.sub.leaf" not in sys.modules

    def test_no_path_walks_and_imports_what_is_on_sys_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        make_package(tmp_path / "syspathpkg")
        monkeypatch.setattr(sys, "path", [str(tmp_path)])
        monkeypatch.delitem(sys.modules, "syspathpkg", raising=False)

        names = [info.name for info in pkgutil.walk_packages()]

        assert names == ["syspathpkg"]
        assert "syspathpkg" in sys.modules
        del sys.modules["syspathpkg"]

    def test_the_generator_does_nothing_until_iterated(
        self, importable: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        top = make_package(importable / "lazytop")
        make_package(top / "sub")
        listdir = CountingListdir()
        monkeypatch.setattr(os, "listdir", listdir)

        walker = pkgutil.walk_packages([str(top)], "lazytop.")

        assert listdir.calls == []
        assert "lazytop.sub" not in sys.modules
        drain(walker)
        assert "lazytop.sub" in sys.modules

    def test_onerror_receives_a_package_that_fails_to_import(
        self, importable: pathlib.Path
    ) -> None:
        top = make_package(importable / "errtop")
        touch(top / "bad" / "__init__.py", "import no_such_module_anywhere\n")
        failed: list[str] = []

        names = [info.name for info in pkgutil.walk_packages([str(top)], "errtop.", failed.append)]

        assert names == ["errtop.bad"]
        assert failed == ["errtop.bad"]

    def test_without_onerror_import_errors_are_skipped_and_others_propagate(
        self, importable: pathlib.Path
    ) -> None:
        top = make_package(importable / "proptop")
        touch(top / "missing" / "__init__.py", "import no_such_module_anywhere\n")
        touch(top / "zbroken" / "__init__.py", "raise RuntimeError('boom')\n")

        walker = pkgutil.walk_packages([str(top)], "proptop.")

        assert next(walker).name == "proptop.missing"
        assert next(walker).name == "proptop.zbroken"
        with pytest.raises(RuntimeError, match="boom"):
            next(walker)

    @staticmethod
    def _walk_peak(top: pathlib.Path, prefix: str) -> int:
        drain(pkgutil.walk_packages([str(top)], prefix))  # imports and finders
        return peak_bytes(lambda: drain(pkgutil.walk_packages([str(top)], prefix)))

    def test_breadth_does_not_raise_the_peak(self, importable: pathlib.Path) -> None:
        one = make_package(importable / "breadthone")
        make_package(one / "p0", modules=400)
        many = make_package(importable / "breadthmany")
        for index in range(40):
            make_package(many / f"p{index}", modules=400)

        one_peak = self._walk_peak(one, "breadthone.")
        many_peak = self._walk_peak(many, "breadthmany.")

        assert many_peak < one_peak * 3, (
            f"40 sibling packages of 400 modules peaked at {many_peak} bytes against "
            f"{one_peak} for one; O(e) space would give about 40x"
        )

    def test_names_from_many_directories_raise_the_peak(self, tmp_path: pathlib.Path) -> None:
        trees = TestIterModulesListsWholeDirectories._trees(tmp_path)
        drain(pkgutil.walk_packages(trees["repeated"]))

        repeated = peak_bytes(lambda: drain(pkgutil.walk_packages(trees["repeated"])))
        distinct = peak_bytes(lambda: drain(pkgutil.walk_packages(trees["distinct"])))

        assert distinct > repeated * 10, (
            f"20,000 distinct names from 100 directories peaked at {distinct} bytes "
            f"against {repeated} for 200 names repeated; the m term is missing"
        )

    def test_depth_raises_the_peak(self, importable: pathlib.Path) -> None:
        shallow = make_package(importable / "depthone")
        make_package(shallow / "p", modules=400)
        deep = make_package(importable / "depthten")
        level = deep
        for _ in range(10):
            level = make_package(level / "p", modules=400)

        shallow_peak = self._walk_peak(shallow, "depthone.")
        deep_peak = self._walk_peak(deep, "depthten.")

        assert deep_peak > shallow_peak * 4, (
            f"ten nested packages of 400 modules peaked at {deep_peak} bytes against "
            f"{shallow_peak} for one; holding one listing at a time would give about 1x"
        )


class TestGetImporterCaches:
    """`get_importer(path_item)` | O(1) | O(1) on a cache hit; a miss asks
    each path hook and caches the finder."""

    def test_a_miss_asks_the_hooks_once_and_a_hit_asks_none(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        finder = object()

        def hook(path: str) -> object:
            calls.append(path)
            return finder

        monkeypatch.setattr(sys, "path_hooks", [hook, *sys.path_hooks])
        monkeypatch.setattr(sys, "path_importer_cache", dict(sys.path_importer_cache))
        item = str(tmp_path)

        assert pkgutil.get_importer(item) is finder
        assert sys.path_importer_cache[item] is finder
        assert pkgutil.get_importer(item) is finder
        assert calls == [item]

    def test_nothing_is_cached_when_no_hook_accepts(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(path: str) -> object:
            raise ImportError(path)

        monkeypatch.setattr(sys, "path_hooks", [refuse])
        monkeypatch.setattr(sys, "path_importer_cache", {})

        assert pkgutil.get_importer(str(tmp_path)) is None
        assert sys.path_importer_cache == {}


class TestIterImportersIsLazy:
    """`iter_importers(fullname='')` | O(s) | O(1): one `get_importer()` per
    entry, taken as it is iterated."""

    def test_one_finder_per_entry_after_the_meta_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = []
        for index in range(5):
            (tmp_path / str(index)).mkdir()
            entries.append(str(tmp_path / str(index)))
        monkeypatch.setattr(sys, "path", entries)
        calls: list[str] = []
        original = pkgutil.get_importer

        def counting(item: str) -> Any:
            calls.append(item)
            return original(item)

        monkeypatch.setattr(pkgutil, "get_importer", counting)

        finders = pkgutil.iter_importers()
        assert calls == []
        found = list(finders)

        assert found[: len(sys.meta_path)] == sys.meta_path
        assert len(found) == len(sys.meta_path) + 5
        assert calls == entries

    def test_a_dotted_name_imports_its_parent(self, importable: pathlib.Path) -> None:
        make_package(importable / "importerpkg")

        found = list(pkgutil.iter_importers("importerpkg.child"))

        assert "importerpkg" in sys.modules
        assert len(found) == len(sys.modules["importerpkg"].__path__) == 1


@pytest.mark.skipif(sys.version_info >= (3, 14), reason="removed in Python 3.14")
class TestLoaderWrappers:
    """`get_loader()` | O(1) imported, O(s) otherwise and `find_loader()` |
    O(s): an imported module's `__loader__`, otherwise one `find_spec()`."""

    @pytest.fixture
    def find_spec_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []
        original = importlib.util.find_spec

        def counting(name: str, package: str | None = None) -> Any:
            calls.append(name)
            return original(name, package)

        monkeypatch.setattr(importlib.util, "find_spec", counting)
        return calls

    def test_an_imported_module_needs_no_search(self, find_spec_calls: list[str]) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            loader = pkgutil.get_loader("json")  # type: ignore[attr-defined]

        assert loader is sys.modules["json"].__loader__
        assert find_spec_calls == []

    def test_a_name_not_imported_is_searched_once(
        self, importable: pathlib.Path, find_spec_calls: list[str]
    ) -> None:
        make_package(importable / "loaderpkg")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            loader = pkgutil.get_loader("loaderpkg")  # type: ignore[attr-defined]
            found = pkgutil.find_loader("loaderpkg")  # type: ignore[attr-defined]

        assert loader is not None and found is not None
        assert find_spec_calls == ["loaderpkg", "loaderpkg"]
        assert "loaderpkg" not in sys.modules

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="deprecated in Python 3.12")
    def test_both_warn(self) -> None:
        with pytest.warns(DeprecationWarning, match="find_spec"):
            pkgutil.get_loader("json")  # type: ignore[attr-defined]
        with pytest.warns(DeprecationWarning, match="find_spec"):
            pkgutil.find_loader("json")  # type: ignore[attr-defined]


@pytest.mark.skipif(sys.version_info < (3, 14), reason="present before Python 3.14")
def test_the_loader_wrappers_are_gone_from_3_14() -> None:
    assert not hasattr(pkgutil, "get_loader")
    assert not hasattr(pkgutil, "find_loader")


@pytest.mark.skipif(sys.version_info >= (3, 12), reason="removed in Python 3.12")
class TestImpEmulation:
    """`ImpImporter` and `ImpLoader` | O(1) | O(1): construction stores its
    arguments and warns."""

    def test_construction_lists_nothing_and_warns(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        listdir = CountingListdir()
        monkeypatch.setattr(os, "listdir", listdir)

        imp_importer: Any = getattr(pkgutil, "ImpImporter")  # noqa: B009 - absent from 3.12
        imp_loader: Any = getattr(pkgutil, "ImpLoader")  # noqa: B009

        with pytest.warns(DeprecationWarning):
            importer = imp_importer(str(tmp_path))
        with pytest.warns(DeprecationWarning):
            loader = imp_loader("name", None, "file.py", ("", "", 0))

        assert listdir.calls == []
        assert importer.path == str(tmp_path)
        assert loader.fullname == "name"


@pytest.mark.skipif(sys.version_info < (3, 12), reason="present before Python 3.12")
def test_the_imp_emulation_is_gone_from_3_12() -> None:
    assert not hasattr(pkgutil, "ImpImporter")
    assert not hasattr(pkgutil, "ImpLoader")


class TestExtendPath:
    """`extend_path(path, name)` | O(s·r) | O(r): one finder lookup per
    search directory, and each portion scans the list built so far."""

    def test_each_portion_scans_the_path_built_so_far(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        search = []
        for index in range(20):
            base = tmp_path / f"base{index}"
            (base / "splitpkg").mkdir(parents=True)
            search.append(str(base))
        monkeypatch.setattr(sys, "path", search)
        original_path = [CountingStr(f"/nowhere/{index}") for index in range(50)]
        lookups: list[str] = []
        original = pkgutil.get_importer

        def counting(item: str) -> Any:
            lookups.append(item)
            return original(item)

        monkeypatch.setattr(pkgutil, "get_importer", counting)
        CountingStr.compared = 0

        extended = pkgutil.extend_path(original_path, "splitpkg")

        assert CountingStr.compared == 20 * 50, f"{CountingStr.compared} comparisons"
        assert lookups == search
        assert extended[50:] == [str(pathlib.Path(base) / "splitpkg") for base in search]

    def test_it_returns_a_copy_and_leaves_a_non_list_alone(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "copypkg").mkdir()
        monkeypatch.setattr(sys, "path", [str(tmp_path)])
        original = ["/nowhere"]
        frozen = ("/nowhere",)

        extended = pkgutil.extend_path(original, "copypkg")

        assert extended == ["/nowhere", str(tmp_path / "copypkg")]
        assert original == ["/nowhere"]
        assert pkgutil.extend_path(frozen, "copypkg") is frozen  # type: ignore[arg-type]


class TestGetDataReadsTheWholeFile:
    """`get_data(package, resource)` | O(s + b) | O(b): the package is
    imported if needed and the resource read into one `bytes`."""

    def test_it_imports_the_package_and_returns_the_bytes(self, importable: pathlib.Path) -> None:
        touch(make_package(importable / "datapkg") / "files" / "a.txt", "hello")

        assert "datapkg" not in sys.modules
        assert pkgutil.get_data("datapkg", "files/a.txt") == b"hello"
        assert "datapkg" in sys.modules

    def test_unknown_package_and_missing_resource(self, importable: pathlib.Path) -> None:
        make_package(importable / "emptypkg")

        assert pkgutil.get_data("no_such_package_here", "x.txt") is None
        with pytest.raises(FileNotFoundError):
            pkgutil.get_data("emptypkg", "missing.txt")

    def test_the_peak_follows_the_file(self, importable: pathlib.Path) -> None:
        package = make_package(importable / "sizepkg")
        (package / "small.bin").write_bytes(b"x" * 4_000)
        (package / "large.bin").write_bytes(b"x" * 4_000_000)
        pkgutil.get_data("sizepkg", "small.bin")

        small_peak = peak_bytes(lambda: pkgutil.get_data("sizepkg", "small.bin"))
        large_peak = peak_bytes(lambda: pkgutil.get_data("sizepkg", "large.bin"))

        assert small_peak < 1_000_000, f"a 4 KB resource peaked at {small_peak} bytes"
        assert large_peak > 4_000_000, f"a 4 MB resource peaked at {large_peak} bytes"


class TestResolveNameImports:
    """`resolve_name(name)` | O(a) imports: one with a colon, one attempt per
    dotted part until one fails without it."""

    @staticmethod
    def _imports(monkeypatch: pytest.MonkeyPatch, name: str) -> tuple[Any, list[str]]:
        calls: list[str] = []
        original = importlib.import_module

        def counting(module: str, package: str | None = None) -> Any:
            calls.append(module)
            return original(module, package)

        monkeypatch.setattr(importlib, "import_module", counting)
        result = pkgutil.resolve_name(name)
        monkeypatch.undo()
        return result, calls

    def test_a_colon_needs_one_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result, calls = self._imports(monkeypatch, "os.path:join.__name__")

        assert result == "join"
        assert calls == ["os.path"]

    def test_without_a_colon_each_part_is_tried_until_one_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._imports(monkeypatch, "os.path.join.__name__")

        assert result == "join"
        assert calls == ["os", "os.path", "os.path.join"]

    def test_a_malformed_name_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid format"):
            pkgutil.resolve_name("not a name")


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
    """Each block runs in its own subprocess and working directory, so the
    packages it creates and the `sys.path` entries it adds cannot leak."""

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
            (n, s) for n, s in _blocks() if "'walkdemo.mod' not in sys.modules" in s
        )
        mutated = source.replace(
            "'walkdemo.mod' not in sys.modules", "'walkdemo.mod' in sys.modules", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
