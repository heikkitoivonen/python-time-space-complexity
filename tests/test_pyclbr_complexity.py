"""Tests for docs/stdlib/pyclbr.md.

The page prices a read as one parse of the source it reaches: the module asked
for plus the modules its top-level imports name, each read once per process
and cached by name. What was read is observed by counting `ast.parse` calls and
by the cache's contents, which needs no tolerance; that the cost is linear in
the source is a timing ratio; what a read keeps against what it passes through
is a traced-allocation comparison at a fixed definition count. Every test runs
against an emptied module cache and restores it afterwards.

Measurement scope:

* Linearity: modules of 500, 2,000 and 8,000 two-line functions are read
  with the garbage collector disabled, fastest of five. Each 4x step costs
  between 2x and 8x, where a quadratic parse would cost 16x.
* Kept against passed through: two modules of 200 functions, one with a
  one-line body and one with 200-line bodies, differ over 100x in traced peak
  while the memory still held with the result differs under 2x.
* The cache: a repeat `readmodule_ex()` parses nothing and returns the same
  dict, even after the file gains a class or when `path` points at another
  file of the same name; in a subprocess, after `importlib.reload(pyclbr)`
  the edit is seen. A repeat `readmodule()` parses nothing, returns a new
  dict each call, and its traced peak grows over 50x from 10 to 5,000 classes.
* Imports: a chain of three modules joined by top-level imports is read in
  three parses; imports under `def`, `class`, `if` and `try`, one after `;`
  on a line, and one naming a missing module, add none. A star import copies
  the other module's entries except those starting with `_`. A `colorsys.py`
  in `path` is read instead of the standard one while `colorsys` is not
  imported; a `bisect.py` there is ignored once `bisect` is imported, and the
  loaded module's file is read. A dotted name parses the package's `__init__.py`
  before the submodule, and the package's result carries `'__path__'`.
* Nothing is executed: a module whose top level raises is read, and neither
  it nor the modules it imports appear in `sys.modules`.
* Empty results: a builtin module gives `{}` without searching the path (the
  path finder is replaced by one that raises); the first extension module in
  `lib-dynload` gives `{}` (skipped where the build has none there), and so
  does a module present only as a `.pyc`, and a package present only as
  `__init__.pyc` gives just `'__path__'`. On 3.11+ each of `os`, `io` and
  `codecs` whose spec origin is `frozen` gives `{}`; on 3.10 `os` is read
  from source and is not empty, as it is on 3.11+ in a subprocess run with
  `-X frozen_modules=off`.
* Every `Class` and `Function` attribute is asserted on a small module:
  resolved and unresolved `super` entries (a base named after an earlier
  function resolves to that `Function`), `methods`, `children`, `parent`,
  `is_async`, `lineno` and `end_lineno`, `file` and `module`, and that
  `readmodule()` keeps only classes. A name defined twice keeps the later
  definition, at top level and in `children`.
* Every fenced Python block runs in its own subprocess, so the module cache
  cannot leak between them, and a mutated assertion in one of them is
  asserted to fail with an `AssertionError`.

Not settled here:

* Locating a module on the search path is outside the bounds by definition;
  path length and directory size are not varied.
* O(1) for attribute reads, for building a `Class` or `Function`, for a
  builtin module and for a cache hit (a dict membership test and lookup) is
  read from Lib/pyclbr.py (3.10 through 3.14 are identical); only the builtin
  module's avoidance of the path search, and a cache hit's avoidance of any
  parse, are observed.
* A dotted base such as `module.Class` whose module was never read is left out
  of `super` altogether rather than kept as a string; the page claims strings
  only for plain names, and only that case is tested.
* A read of a module (not a package) that raises `SyntaxError` leaves an
  empty dict cached under the name, so a later call returns `{}`; the page does not document that case.
* No bound is given for walking a result: an entry bound by `from ... import`
  can make one definition reachable under several names.
* Relative imports, star-import sizes, many bases on one class, `ast.unparse`
  cost for long base expressions, and the width of source lines are not
  varied.
"""

from __future__ import annotations

import ast
import gc
import importlib
import importlib.machinery
import importlib.util
import pathlib
import py_compile
import pyclbr
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pyclbr.md"
EXPECTED_BLOCKS = 5


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds, with the collector off."""
    best: float | None = None
    enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            func()
            elapsed = time.perf_counter_ns() - start
            best = elapsed if best is None else min(best, elapsed)
    finally:
        if enabled:
            gc.enable()
    assert best is not None
    return best


def memory(func: Callable[[], Any]) -> tuple[int, int]:
    """Traced (held afterwards, peak) while func runs; func's result is kept alive."""
    tracemalloc.start()
    try:
        result = func()
        held, peak = tracemalloc.get_traced_memory()
        del result
        return held, peak
    finally:
        tracemalloc.stop()


def cache() -> dict[str, Any]:
    return vars(pyclbr)["_modules"]


@pytest.fixture(autouse=True)
def empty_cache() -> Iterator[None]:
    saved = dict(cache())
    cache().clear()
    yield
    cache().clear()
    cache().update(saved)


def write(directory: pathlib.Path, files: dict[str, str]) -> list[str]:
    for name, text in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(text))
    importlib.invalidate_caches()
    return [str(directory)]


@pytest.fixture
def parses(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the filename of every source pyclbr parses."""
    seen: list[str] = []
    real = vars(pyclbr)["_create_tree"]

    def counting(fullmodule: str, path: Any, fname: str, *rest: Any) -> Any:
        seen.append(pathlib.Path(fname).name if fname else fullmodule)
        return real(fullmodule, path, fname, *rest)

    monkeypatch.setattr(pyclbr, "_create_tree", counting)
    return seen


def functions(count: int, body: int = 1) -> str:
    lines = [
        f"def f{i}(a, b):\n" + "".join(f"    x{j} = a + b + {j}\n" for j in range(body))
        for i in range(count)
    ]
    return "".join(lines)


class TestReadingParsesWithoutExecuting:
    """`readmodule_ex()`: 'Parses without executing'. A top level that raises
    would stop an import; the read succeeds and nothing is imported."""

    def test_a_module_that_would_exit_is_still_described(self, tmp_path: pathlib.Path) -> None:
        path = write(
            tmp_path,
            {
                "exits.py": """\
                    import exits_helper
                    raise SystemExit('ran')
                    class Kept:
                        pass
                    """,
                "exits_helper.py": "VALUE = 1\n",
            },
        )
        tree = pyclbr.readmodule_ex("exits", path)

        assert list(tree) == ["Kept"]
        assert "exits" not in sys.modules
        assert "exits_helper" not in sys.modules

    def test_it_parses_through_ast(self, tmp_path: pathlib.Path, monkeypatch: Any) -> None:
        path = write(tmp_path, {"parsed.py": "class A:\n    pass\n"})
        calls: list[int] = []
        real = ast.parse

        def counting(source: Any, *args: Any, **kwargs: Any) -> Any:
            calls.append(len(source))
            return real(source, *args, **kwargs)

        monkeypatch.setattr(ast, "parse", counting)
        pyclbr.readmodule_ex("parsed", path)

        assert calls == [len("class A:\n    pass\n")]

    def test_readmodule_keeps_only_top_level_classes(self, tmp_path: pathlib.Path) -> None:
        path = write(tmp_path, {"mixed.py": "class A:\n    pass\ndef f():\n    pass\n"})

        assert list(pyclbr.readmodule_ex("mixed", path)) == ["A", "f"]
        assert list(pyclbr.readmodule("mixed", path)) == ["A"]


@pytest.mark.timing
class TestReadingIsLinearInTheSource:
    """`readmodule_ex()` is O(s). Each 4x step in source costs about 4x;
    a quadratic parse or walk would cost 16x."""

    def test_four_times_the_source_costs_about_four_times(self, tmp_path: pathlib.Path) -> None:
        sizes = (500, 2_000, 8_000)
        path = write(tmp_path, {f"lin{n}.py": functions(n) for n in sizes})

        def read(name: str) -> Callable[[], Any]:
            def run() -> Any:
                cache().clear()
                return pyclbr.readmodule_ex(name, path)

            return run

        times = [best_ns(read(f"lin{n}")) for n in sizes]
        ratios = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]

        assert all(2 < r < 8 for r in ratios), f"times={times} ratios={ratios}"


@pytest.mark.serial
class TestTheResultKeepsDefinitionsNotSource:
    """`readmodule_ex()` space: O(s) at the peak, O(d) kept. At a fixed 200
    definitions, 200x the body lines moves the peak far more than what is
    held with the result."""

    def test_the_peak_follows_the_source_and_the_kept_part_does_not(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = write(
            tmp_path,
            {"thin.py": functions(200, body=1), "fat.py": functions(200, body=200)},
        )

        thin_held, thin_peak = memory(lambda: pyclbr.readmodule_ex("thin", path))
        fat_held, fat_peak = memory(lambda: pyclbr.readmodule_ex("fat", path))

        assert fat_peak > 100 * thin_peak, (thin_peak, fat_peak)
        assert fat_held < 2 * thin_held, (thin_held, fat_held)

    def test_one_object_per_definition_nested_ones_included(self, tmp_path: pathlib.Path) -> None:
        path = write(
            tmp_path,
            {
                "nested.py": """\
                    class A:
                        def m(self):
                            def inner():
                                pass
                        class B:
                            async def n(self):
                                pass
                    """
            },
        )
        tree = pyclbr.readmodule_ex("nested", path)

        def walk(objects: dict[str, Any]) -> Iterator[Any]:
            for obj in objects.values():
                yield obj
                yield from walk(obj.children)

        kinds = sorted((type(o).__name__, o.name) for o in walk(tree))
        assert kinds == [
            ("Class", "A"),
            ("Class", "B"),
            ("Function", "inner"),
            ("Function", "m"),
            ("Function", "n"),
        ]


class TestTheModuleCache:
    """'Results are cached by module name for the life of the process and
    returned as the same dict, even after the file changes or with a
    different `path`'; `readmodule()` builds a new dict of classes each call."""

    def test_a_repeat_parses_nothing_and_returns_the_same_dict(
        self, tmp_path: pathlib.Path, parses: list[str]
    ) -> None:
        path = write(tmp_path, {"again.py": "class A:\n    pass\n"})
        first = pyclbr.readmodule_ex("again", path)
        second = pyclbr.readmodule_ex("again", path)

        assert second is first
        assert parses == ["again.py"]

    def test_an_edit_is_not_seen(self, tmp_path: pathlib.Path) -> None:
        path = write(tmp_path, {"edited.py": "class A:\n    pass\n"})
        pyclbr.readmodule_ex("edited", path)
        write(tmp_path, {"edited.py": "class A:\n    pass\nclass B:\n    pass\n"})

        assert list(pyclbr.readmodule_ex("edited", path)) == ["A"]

    def test_a_different_path_gets_the_first_file(self, tmp_path: pathlib.Path) -> None:
        one = write(tmp_path / "one", {"same.py": "class One:\n    pass\n"})
        two = write(tmp_path / "two", {"same.py": "class Two:\n    pass\n"})
        pyclbr.readmodule_ex("same", one)

        assert list(pyclbr.readmodule_ex("same", two)) == ["One"]

    def test_reloading_pyclbr_starts_an_empty_cache(self, tmp_path: pathlib.Path) -> None:
        script = textwrap.dedent(
            """\
            import importlib, pathlib, pyclbr, sys
            directory = sys.argv[1]
            target = pathlib.Path(directory, "reloaded.py")
            target.write_text("class A:\\n    pass\\n")
            pyclbr.readmodule_ex("reloaded", [directory])
            target.write_text("class A:\\n    pass\\nclass B:\\n    pass\\n")
            assert list(pyclbr.readmodule_ex("reloaded", [directory])) == ["A"]
            importlib.reload(pyclbr)
            assert list(pyclbr.readmodule_ex("reloaded", [directory])) == ["A", "B"]
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr

    def test_readmodule_reuses_the_read_but_builds_a_new_dict(
        self, tmp_path: pathlib.Path, parses: list[str]
    ) -> None:
        path = write(tmp_path, {"classes.py": "class A:\n    pass\n"})
        first = pyclbr.readmodule("classes", path)
        second = pyclbr.readmodule("classes", path)

        assert first == second
        assert first is not second
        assert parses == ["classes.py"]

    @pytest.mark.serial
    def test_a_repeat_readmodule_grows_with_the_top_level_entries(
        self, tmp_path: pathlib.Path
    ) -> None:
        many = "".join(f"class C{i}:\n    pass\n" for i in range(5_000))
        few = "".join(f"class C{i}:\n    pass\n" for i in range(10))
        path = write(tmp_path, {"many.py": many, "few.py": few})
        pyclbr.readmodule("many", path)
        pyclbr.readmodule("few", path)

        _, few_peak = memory(lambda: pyclbr.readmodule("few", path))
        _, many_peak = memory(lambda: pyclbr.readmodule("many", path))

        assert many_peak > 50 * max(few_peak, 1), (few_peak, many_peak)


class TestImportsAreFollowed:
    """'An absolute `import` or `from ... import` at column 0 reads the named
    module too, transitively; imports nested in a `def`, `class`, `if` or `try`
    are not followed.' Parses are counted by file."""

    def test_a_chain_of_top_level_imports_is_read_to_its_end(
        self, tmp_path: pathlib.Path, parses: list[str]
    ) -> None:
        path = write(
            tmp_path,
            {
                "head.py": "import middle\n",
                "middle.py": "from tail import Tail\n",
                "tail.py": "class Tail:\n    pass\n",
            },
        )
        pyclbr.readmodule_ex("head", path)

        assert sorted(parses) == ["head.py", "middle.py", "tail.py"]

    def test_nested_and_missing_imports_are_not_read(
        self, tmp_path: pathlib.Path, parses: list[str]
    ) -> None:
        path = write(
            tmp_path,
            {
                "outer.py": """\
                    import not_a_module_anywhere
                    if True:
                        import skipped_if
                    try:
                        import skipped_try
                    except ImportError:
                        pass
                    def f():
                        import skipped_def
                    class C:
                        import skipped_class
                    X = 1; import skipped_semicolon
                    """,
                **{
                    f"skipped_{k}.py": "X = 1\n" for k in ("if", "try", "def", "class", "semicolon")
                },
            },
        )
        pyclbr.readmodule_ex("outer", path)

        assert parses == ["outer.py"]

    def test_from_import_binds_the_other_module_s_class(self, tmp_path: pathlib.Path) -> None:
        path = write(
            tmp_path,
            {
                "lib.py": "class Base:\n    pass\n",
                "user.py": "from lib import Base\nclass User(Base):\n    pass\n",
            },
        )
        tree: dict[str, Any] = pyclbr.readmodule_ex("user", path)

        assert tree["Base"] is pyclbr.readmodule_ex("lib", path)["Base"]
        assert tree["User"].super == [tree["Base"]]

    def test_a_dotted_name_reads_the_package_first(
        self, tmp_path: pathlib.Path, parses: list[str]
    ) -> None:
        path = write(
            tmp_path,
            {
                "pkg/__init__.py": "class Package:\n    pass\n",
                "pkg/mod.py": "class Mod:\n    pass\n",
            },
        )
        tree = pyclbr.readmodule_ex("pkg.mod", path)

        assert parses == ["__init__.py", "mod.py"]
        assert list(tree) == ["Mod"]
        package = pyclbr.readmodule_ex("pkg", path)
        assert package["__path__"] == [str(tmp_path / "pkg")]
        assert "Package" in package

    def test_a_star_import_copies_the_public_entries(self, tmp_path: pathlib.Path) -> None:
        path = write(
            tmp_path,
            {
                "star_source.py": "class Public:\n    pass\nclass _Private:\n    pass\n",
                "star_user.py": "from star_source import *\n",
            },
        )

        assert list(pyclbr.readmodule_ex("star_user", path)) == ["Public"]

    def test_path_is_searched_before_sys_path(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delitem(sys.modules, "colorsys", raising=False)
        path = write(tmp_path, {"colorsys.py": "class Shadow:\n    pass\n"})
        tree: dict[str, Any] = pyclbr.readmodule_ex("colorsys", path)

        assert list(tree) == ["Shadow"]
        assert tree["Shadow"].file == str(tmp_path / "colorsys.py")

    def test_an_imported_module_is_read_from_its_own_file(self, tmp_path: pathlib.Path) -> None:
        importlib.import_module("bisect")
        path = write(tmp_path, {"bisect.py": "class Shadow:\n    pass\n"})
        tree = pyclbr.readmodule_ex("bisect", path)

        assert "Shadow" not in tree
        assert "insort_right" in tree


class TestModulesWithoutSource:
    """'A builtin module, or one with no Python source to read': an empty
    dict; from 3.11 a frozen standard module is one of them."""

    def test_a_builtin_module_is_empty_without_searching(self, monkeypatch: Any) -> None:
        assert "sys" in sys.builtin_module_names

        def refuse(*args: Any) -> Any:
            raise AssertionError("searched the path for a builtin")

        monkeypatch.setattr(importlib.util, "_find_spec_from_path", refuse)
        assert pyclbr.readmodule_ex("sys") == {}

    def test_an_extension_module_is_empty(self) -> None:
        dynload = [pathlib.Path(p) for p in sys.path if p.endswith("lib-dynload")]
        names = sorted(
            path.name.split(".")[0]
            for directory in dynload
            for path in directory.glob("*.so")
            if not path.name.startswith("_test")
        )
        spec = next(
            (
                spec
                for spec in map(importlib.util.find_spec, names)
                if spec is not None
                and isinstance(spec.loader, importlib.machinery.ExtensionFileLoader)
            ),
            None,
        )
        if spec is None:
            pytest.skip("this interpreter has no extension modules outside the binary")
        assert pyclbr.readmodule_ex(spec.name) == {}

    def test_a_module_with_only_bytecode_is_empty(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "compiled.py"
        source.write_text("class Hidden:\n    pass\n")
        py_compile.compile(str(source), cfile=str(tmp_path / "compiled.pyc"), doraise=True)
        source.unlink()
        importlib.invalidate_caches()

        assert pyclbr.readmodule_ex("compiled", [str(tmp_path)]) == {}

    def test_a_package_with_only_bytecode_keeps_its_path(self, tmp_path: pathlib.Path) -> None:
        package = tmp_path / "bytepkg"
        package.mkdir()
        source = package / "__init__.py"
        source.write_text("class Hidden:\n    pass\n")
        py_compile.compile(str(source), cfile=str(package / "__init__.pyc"), doraise=True)
        source.unlink()
        importlib.invalidate_caches()

        assert pyclbr.readmodule_ex("bytepkg", [str(tmp_path)]) == {"__path__": [str(package)]}

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="frozen os starts in 3.11")
    def test_a_frozen_module_is_empty(self) -> None:
        frozen = [
            name
            for name in ("os", "io", "codecs")
            if getattr(importlib.util.find_spec(name), "origin", None) == "frozen"
        ]
        if not frozen:
            pytest.skip("this interpreter does not run os, io or codecs frozen")
        assert {name: pyclbr.readmodule_ex(name) for name in frozen} == dict.fromkeys(frozen, {})

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="frozen os starts in 3.11")
    def test_turning_frozen_modules_off_reads_os_from_source(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "frozen_modules=off",
                "-c",
                "import pyclbr; assert 'walk' in pyclbr.readmodule_ex('os')",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 reads os from source")
    def test_os_is_read_from_source_on_310(self) -> None:
        assert "walk" in pyclbr.readmodule_ex("os")


class TestClassAndFunctionAttributes:
    """The Class and Function rows: stored values, `parent`, `super`,
    `methods`, `children` and `is_async`."""

    SOURCE = """\
        class Known:
            pass

        class Node(Known, Unknown):
            def walk(self):
                def visit():
                    pass

            async def fetch(self):
                pass

            class Meta:
                pass

        async def top():
            pass
        """

    @pytest.fixture
    def tree(self, tmp_path: pathlib.Path) -> dict[str, Any]:
        return pyclbr.readmodule_ex("attrs", write(tmp_path, {"attrs.py": self.SOURCE}))

    def test_stored_values(self, tree: dict[str, Any], tmp_path: pathlib.Path) -> None:
        node = tree["Node"]
        assert isinstance(node, pyclbr.Class)
        assert (node.name, node.module, node.lineno, node.end_lineno) == ("Node", "attrs", 4, 13)
        assert node.file == str(tmp_path / "attrs.py")
        top = tree["top"]
        assert isinstance(top, pyclbr.Function)
        assert (top.name, top.module, top.lineno, top.end_lineno) == ("top", "attrs", 15, 16)
        assert top.file == node.file

    def test_super_resolves_known_names_and_keeps_the_rest_as_strings(
        self, tree: dict[str, Any]
    ) -> None:
        assert tree["Node"].super == [tree["Known"], "Unknown"]
        assert tree["Known"].super == []

    def test_super_holds_whatever_the_name_resolved_to(self, tmp_path: pathlib.Path) -> None:
        source = "def Base():\n    pass\nclass C(Base):\n    pass\n"
        tree: dict[str, Any] = pyclbr.readmodule_ex("odd", write(tmp_path, {"odd.py": source}))

        assert tree["C"].super == [tree["Base"]]
        assert isinstance(tree["Base"], pyclbr.Function)

    def test_a_name_defined_twice_keeps_the_later_definition(self, tmp_path: pathlib.Path) -> None:
        source = textwrap.dedent(
            """\
            def f():
                pass
            class K:
                def m(self):
                    pass
                def m(self):
                    pass
            def f():
                pass
            """
        )
        tree: dict[str, Any] = pyclbr.readmodule_ex("twice", write(tmp_path, {"twice.py": source}))

        assert tree["f"].lineno == 8
        assert tree["K"].children["m"].lineno == 6
        assert tree["K"].methods == {"m": 6}

    def test_methods_leave_out_functions_inside_methods(self, tree: dict[str, Any]) -> None:
        assert tree["Node"].methods == {"walk": 5, "fetch": 9}
        assert tree["Node"].children["Meta"].methods == {}

    def test_children_and_parent_link_the_nesting(self, tree: dict[str, Any]) -> None:
        node = tree["Node"]
        assert list(node.children) == ["walk", "fetch", "Meta"]
        walk = node.children["walk"]
        assert list(walk.children) == ["visit"]
        assert walk.children["visit"].parent is walk
        assert walk.parent is node
        assert node.children["Meta"].parent is node
        assert node.parent is None and tree["top"].parent is None
        assert "walk" not in tree

    def test_is_async(self, tree: dict[str, Any]) -> None:
        node = tree["Node"]
        assert tree["top"].is_async is True
        assert node.children["fetch"].is_async is True
        assert node.children["walk"].is_async is False


def _blocks() -> list[tuple[int, str]]:
    text = PAGE.read_text()
    blocks: list[tuple[int, str]] = []
    for match in re.finditer(r"^```python\n(.*?)^```", text, re.M | re.S):
        line = text.count("\n", 0, match.start()) + 1
        blocks.append((line, textwrap.dedent(match.group(1))))
    return blocks


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, so the
    module cache cannot leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert again is first" in s)
        mutated = source.replace("assert again is first", "assert again is not first", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr, result.stderr
