"""Tests for docs/stdlib/pydoc.md.

The page prices `pydoc` by what it documents: a module costs its sorted
members and the text produced, a class its attributes times the square of
its MRO depth, and a search every module on `sys.path`. Most claims are
settled by observation - a counting `__eq__`, a counting wrapper around a
`pydoc` or `inspect` helper, a log line written each time a module runs, or
which names end up in `sys.modules`. Timing is used only for the growth
classes counting cannot reach; growth tests compare sizes 4x or 8x apart,
and one compares 50,000 subclasses with none.

Measurement scope:

* Module rendering: `visiblename()` is called a fixed number of times per
  member, so the count grows between 8x and 12x from 100 to 1,000
  functions, and a second render of the same module makes the same number
  of calls. An `__all__` list of counting strings shows `name in __all__`
  comparing against the list once per member: 200 members make more than
  10,000 comparisons, 400 make more than 3.5 times as many, a tuple behaves
  like the list, and a set `__all__` of the same names makes fewer than
  400. A timing test renders modules of 500, 2,000 and 8,000 functions with
  no `__all__`; each 4x step costs between 2x and 8x, against 16x for a
  quadratic.
* Class rendering: a metaclass counting attribute lookups sees more than
  50 x 50 of them for 50 attributes at MRO depth 50, and more than ten
  times the count at depth 2, in both renderers. In timing tests with 100
  attributes on the root class, depth 800 costs more than 8x depth 200
  (x16.2-16.9 measured on 3.10, 3.12 and 3.14) while the output grows less
  than 3x; at depth 200, 400 attributes cost between 2x and 8x 100
  attributes; a class with 50,000 direct subclasses costs the text renderer
  more than 5x one with none. The d² term comes from type lookups that miss the
  interpreter's 4,096-entry type cache (MCACHE_SIZE_EXP 12 in
  Objects/typeobject.c on 3.10-3.14) and walk the MRO: both timing tests
  have a·d of 20,000 pairs or more, and the size at which the cache stops
  holding them is not varied.
* `TextDoc.formattree()` over 8,000 top-level classes costs more than 24x
  its cost over 1,000, as does `HTMLDoc.formattree()` over 8,000 classes
  with two listed bases against 1,000, and `HTMLDoc.multicolumn()` over
  16,000 items against 2,000; 8x the input predicts x8 for linear and x64
  for quadratic, and 3.10-3.14 measured x68-x88, x44-x126 and x59-x81.
* `getdoc()` without a docstring: rendering a file module of 30 classes
  without docstrings calls `ast.parse()` 30 times on Python 3.10-3.12 and
  never on 3.13+; with docstrings, never on any version. Two undocumented
  functions in one file load it into `linecache` once.
* Naming: `locate('json.decoder.JSONDecoder.decode')` calls `safeimport()`
  for exactly three prefixes; `resolve()` of an object calls it for none.
  A module that appends to a log file when it runs is run once by two
  `render_doc()` calls, again by `forceload=1`, again by every
  `importfile()`, and again by every server page request, which goes
  through `_url_handler()` as the server does. `forceload` drops a
  package's imported submodules from `sys.modules` and leaves `sys` in
  place. `safeimport()` returns `None` for a missing module and raises
  `ErrorDuringImport` for a missing parent package.
* `writedoc()` and `writedocs()` write `<name>.html` into the current
  directory; with the source directory off `sys.path`, `writedocs()` raises
  `ImportError` on 3.11+ and prints the message on 3.10, as `doc()` with
  `output` writes or prints it.
* Searching runs on a `sys.path` holding only a temporary directory, with
  `sys.builtin_module_names` emptied in-process so the built-in loop cannot
  import anything. Without a key, a package is imported and its plain
  submodule is not. With a key, `source_synopsis()` receives the whole
  source of a module whose docstring is followed by 200,000 characters,
  on each of two scans. The server's search page lists the same match.
  In a subprocess recording `__import__`, a scan with a key asks for every
  built-in module and one without asks for none. Setting `quit` from the
  callback stops the walk after the first module, and does not stop the
  built-in loop. `apropos()` and `Helper.listmodules(key)` print
  to `sys.stdout`, matching case-insensitively.
* `synopsis()` opens a file once for two calls, again after its
  modification time moves forward, not after it moves back, and runs a
  `.pyc` file it is given; `source_synopsis()` asks for at most
  five lines of a 10,000-line file, with a docstring first or a statement
  first. Class sorting by `_fields` (O(a log a)) and the HTML column layout
  of a module's submodules are read from Lib/pydoc.py; the column layout's
  O(k²) is the `multicolumn()` test.
* Helper: keyword lists, object help and module lists go to `output`; topic
  texts go there from 3.12.5 and to the pager before; `interact()` given a
  stream asks for another line after the stream ends from 3.13.12 and
  3.14.3, observed by counting `getline()` calls.
* Rendering helpers: a package's text page lists a submodule whose import
  would raise; `HTMLDoc.index()` shows a subdirectory holding `__init__.py`
  as a package and omits one without; `getdocloc()` links `json` to
  docs.python.org, or below `PYTHONDOCS` when set, and a temporary module
  to nothing.
* Pagers: the five old names exist on every version and, from 3.13, are
  aliases of the new ones, and the plain pager takes a title; in a fresh
  interpreter `pydoc.pager()` consults `get_pager()` once over three calls
  and ends up as the plain pager; `pipe_pager()` and `tempfile_pager()`
  hand the text to a command; `tty_pager()` with `LINES=5` shows four
  lines and stops at `q`.
* Reprs: the limits pydoc does not set equal `reprlib.Repr()`'s;
  `TextRepr.repr_string()` of a 10,000,000-character string peaks
  under 10 KB; `TextRepr.repr1()` of a 1,000,000-byte `bytes` peaks over
  1 MB.
* The server: `_start_server()` builds an `http.server.HTTPServer` that is
  not a `ThreadingMixIn`, and serves a module page to `urllib`;
  `python -m pydoc -p 0` with `q` on stdin prints its URL and stops.
  `cli()` run with the current directory removed from `sys.path` puts it
  back first and finds a module there.
* Every fenced Python block runs in its own subprocess on the pinned
  interpreter, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(M log M) term is the sort inside `inspect.getmembers()`; the timing
  test cannot tell it from O(M).
* Import cost, which the page excludes, and the cost of each routine's
  `inspect.signature()`, which it counts in w.
* `get_pager()` on a real terminal: it may run `pager`, `less` or `more`
  through `os.system`, and the tests have no terminal. `tty_pager()` is
  driven through `readline()`, not `tty.setcbreak()`.
* `browse()` opening a web browser, and `-b`; the server's per-request
  rendering is observed through its handler, not by timing requests.
* `pydoc.help(request)` with no `output`, which pages through the
  terminal; it is the same `Helper.help()` the tests drive with `output`.
* Windows: `tempfile_pager()` is what `get_pager()` picks on a Windows
  terminal with `PAGER` set or none, and paths are compared
  case-insensitively; neither is varied. The pager tests'
  shell commands are quoted for the platform they run on.
* Docstring length, signature width, `__all__` order and import side
  effects other than running the module are held fixed.
"""

from __future__ import annotations

import ast
import collections
import inspect
import io
import linecache
import os
import pathlib
import py_compile
import pydoc
import re
import reprlib
import shlex
import socketserver
import subprocess
import sys
import textwrap
import time
import tokenize
import tracemalloc
import types
import urllib.request
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pydoc.md"
EXPECTED_BLOCKS = 8

# typeshed does not declare these; the tests read them from the module itself.
PLAINTEXT: Any = vars(pydoc)["plaintext"]
SORT_ATTRIBUTES: Any = vars(pydoc)["sort_attributes"]


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def run_python(source: str, cwd: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a script in a fresh interpreter with no terminal on stdin."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def shell_command(*argv: str) -> str:
    """A shell command line that runs argv, quoted for this platform's shell."""
    if sys.platform == "win32":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


@pytest.fixture
def source_dir(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[pathlib.Path]:
    """A directory on the front of sys.path whose modules are forgotten afterwards."""
    directory = tmp_path / "src"
    directory.mkdir()
    monkeypatch.syspath_prepend(str(directory))
    before = set(sys.modules)
    yield directory
    for name in set(sys.modules) - before:
        del sys.modules[name]


def logging_module(directory: pathlib.Path, name: str) -> pathlib.Path:
    """Write a module that appends a line to <name>.log each time it runs."""
    log = directory / f"{name}.log"
    (directory / f"{name}.py").write_text(
        f'"""Logs every run."""\nwith open({str(log)!r}, "a") as f:\n    f.write("run\\n")\n',
        encoding="utf-8",
    )
    return log


def runs(log: pathlib.Path) -> int:
    return log.read_text(encoding="utf-8").count("run") if log.exists() else 0


def function_module(
    monkeypatch: pytest.MonkeyPatch, count: int, all_names: Any = None
) -> types.ModuleType:
    """A module of `count` functions, registered so `inspect.getmodule()` finds their home."""
    module = types.ModuleType(f"probe_{count}")
    exec("\n".join(f"def f{i}(a, b=1):\n    'doc'\n" for i in range(count)), module.__dict__)
    if all_names is not None:
        module.__dict__["__all__"] = all_names
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


def deep_class(depth: int, attributes: int) -> type:
    """A chain of `depth` documented classes whose root defines every attribute."""
    cls = type("Root", (), {"__doc__": "Root.", **{f"m{i}": i for i in range(attributes)}})
    for level in range(1, depth):
        cls = type(f"Level{level}", (cls,), {"__doc__": "Level."})
    return cls


class CountingStr(str):
    comparisons = 0

    def __eq__(self, other: object) -> bool:
        CountingStr.comparisons += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


class TestModuleRenderingFollowsMembers:
    """D for a module: O(M log M + C² + w), plus O(M·L) for a list or tuple
    `__all__`, since every member is checked with `name in __all__`. These
    modules hold functions only, so C is 0."""

    @pytest.fixture(autouse=True)
    def _keep_monkeypatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch

    def count_visibility_checks(self, monkeypatch: pytest.MonkeyPatch, module: Any) -> int:
        calls = 0
        original = pydoc.visiblename

        def counting(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(pydoc, "visiblename", counting)
        PLAINTEXT.document(module)
        monkeypatch.setattr(pydoc, "visiblename", original)
        return calls

    def test_each_member_is_checked_a_fixed_number_of_times(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        small = self.count_visibility_checks(monkeypatch, function_module(monkeypatch, 100))
        large = self.count_visibility_checks(monkeypatch, function_module(monkeypatch, 1_000))

        assert small >= 100, "the functions were not documented"
        again = self.count_visibility_checks(monkeypatch, sys.modules["probe_100"])
        assert again == small, "a second render repeats the walk"

        assert 8 * small < large < 12 * small, (small, large)

    def comparisons(self, members: int, all_names: Any) -> int:
        module = function_module(self.monkeypatch, members, all_names)
        CountingStr.comparisons = 0
        text = PLAINTEXT.document(module)
        assert f"f{members - 1}(a, b=1)" in text
        return CountingStr.comparisons

    def test_a_list_all_is_searched_once_per_member(self) -> None:
        small = self.comparisons(200, [CountingStr(f"f{i}") for i in range(200)])
        large = self.comparisons(400, [CountingStr(f"f{i}") for i in range(400)])

        assert small > 200 * 200 / 4, small
        assert large > 3.5 * small, (small, large)

    def test_a_tuple_all_is_searched_the_same_way(self) -> None:
        names = tuple(CountingStr(f"f{i}") for i in range(200))

        assert self.comparisons(200, names) > 200 * 200 / 4

    def test_a_set_all_is_not_searched(self) -> None:
        names = {CountingStr(f"f{i}") for i in range(200)}

        assert self.comparisons(200, names) < 2 * 200

    def test_all_decides_what_is_shown(self) -> None:
        module = function_module(self.monkeypatch, 3, ["f1"])

        text = PLAINTEXT.document(module)

        assert "f1(a, b=1)" in text
        assert "f0(" not in text
        assert "f2(" not in text

    @pytest.mark.timing
    def test_documenting_a_module_grows_near_linearly(self) -> None:
        modules = [function_module(self.monkeypatch, n) for n in (500, 2_000, 8_000)]
        assert "f7999(a, b=1)" in PLAINTEXT.document(modules[-1])
        durations = [best_ns(lambda m=m: PLAINTEXT.document(m), repeats=3) for m in modules]
        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]

        assert all(2 < ratio < 8 for ratio in ratios), (
            f"4x the members cost {[f'x{r:.2f}' for r in ratios]}; "
            "linear predicts x4 and quadratic x16"
        )


class TestClassRenderingIsAttributesTimesDepthSquared:
    """D for a class: O(a·d² + w). Each attribute is looked up on every class
    in the MRO, and a lookup the type cache misses walks that class's MRO."""

    @pytest.mark.parametrize("renderer", [PLAINTEXT, pydoc.html], ids=["text", "html"])
    def test_each_attribute_is_looked_up_on_every_mro_class(self, renderer: Any) -> None:
        class Counting(type):
            lookups = 0

            def __getattribute__(cls, name: str) -> Any:
                Counting.lookups += 1
                return super().__getattribute__(name)

        totals = []
        for depth in (2, 50):
            cls = Counting("Root", (), {f"m{i}": i for i in range(50)})
            for level in range(1, depth):
                cls = Counting(f"Level{level}", (cls,), {})
            Counting.lookups = 0
            renderer.document(cls)
            totals.append(Counting.lookups)

        assert totals[1] > 50 * 50, totals
        assert totals[1] > 10 * totals[0], totals

    @pytest.mark.timing
    def test_four_times_the_depth_costs_sixteen_times_as_much(self) -> None:
        shallow, deep = deep_class(200, 100), deep_class(800, 100)
        sizes = [len(PLAINTEXT.document(cls)) for cls in (shallow, deep)]

        durations = [best_ns(lambda c=cls: PLAINTEXT.document(c)) for cls in (shallow, deep)]

        assert sizes[1] < 3 * sizes[0], sizes
        ratio = durations[1] / durations[0]
        assert ratio > 8, (
            f"4x the depth at 100 attributes cost x{ratio:.2f}; O(a·d) predicts x4, O(a·d²) x16"
        )

    @pytest.mark.timing
    def test_the_text_renderer_scans_direct_subclasses(self) -> None:
        # Docstrings keep 3.10-3.12 from parsing this file for each class.
        lonely = type("Lonely", (), {"__doc__": "Alone."})
        popular = type("Popular", (), {"__doc__": "Liked."})
        children = [type(f"Child{i}", (popular,), {}) for i in range(50_000)]

        durations = [best_ns(lambda c=cls: PLAINTEXT.document(c)) for cls in (lonely, popular)]

        assert len(children) == len(popular.__subclasses__())
        ratio = durations[1] / durations[0]
        assert ratio > 5, f"50,000 subclasses cost x{ratio:.1f} over none"

    @pytest.mark.timing
    def test_four_times_the_attributes_cost_four_times_as_much(self) -> None:
        narrow, wide = deep_class(200, 100), deep_class(200, 400)

        durations = [best_ns(lambda c=cls: PLAINTEXT.document(c)) for cls in (narrow, wide)]

        ratio = durations[1] / durations[0]
        assert 2 < ratio < 8, f"4x the attributes at depth 200 cost x{ratio:.2f}; linear is x4"

    def test_inherited_attributes_are_labelled_by_their_class(self) -> None:
        text = PLAINTEXT.document(deep_class(3, 2))

        assert "Method resolution order:" in text
        assert "Data and other attributes inherited from Root:" in text


class TestTreesAndColumnsCopyTheTextSoFar:
    """`formattree()` is O(k²) - always in text, and in HTML where a class's
    bases are listed - and `HTMLDoc.multicolumn()` is O(k²): each line is
    appended by copying the text built so far."""

    @staticmethod
    def ratio(small: Any, large: Any, render: Callable[[Any], Any]) -> float:
        return best_ns(lambda: render(large)) / best_ns(lambda: render(small))

    @staticmethod
    def flat_tree(count: int) -> Any:
        return inspect.getclasstree([type(f"C{i}", (), {}) for i in range(count)], True)

    @staticmethod
    def two_base_tree(count: int) -> Any:
        first, second = type("First", (), {}), type("Second", (), {})
        classes = [first, second] + [type(f"C{i}", (first, second), {}) for i in range(count)]
        return inspect.getclasstree(classes, True)

    def test_the_trees_list_every_class(self) -> None:
        assert PLAINTEXT.formattree(self.flat_tree(3), "__main__").count("C") == 3
        assert pydoc.html.formattree(self.two_base_tree(3), "__main__").count("First") > 3

    @pytest.mark.timing
    def test_the_text_tree_is_quadratic(self) -> None:
        ratio = self.ratio(
            self.flat_tree(1_000),
            self.flat_tree(8_000),
            lambda tree: PLAINTEXT.formattree(tree, "__main__"),
        )

        assert ratio > 24, f"8x the classes cost x{ratio:.1f}; linear is x8, quadratic x64"

    @pytest.mark.timing
    def test_the_html_tree_with_listed_bases_is_quadratic(self) -> None:
        ratio = self.ratio(
            self.two_base_tree(1_000),
            self.two_base_tree(8_000),
            lambda tree: pydoc.html.formattree(tree, "__main__"),
        )

        assert ratio > 24, f"8x the classes cost x{ratio:.1f}; linear is x8, quadratic x64"

    @pytest.mark.timing
    def test_multicolumn_is_quadratic(self) -> None:
        ratio = self.ratio(
            [f"name{i}" for i in range(2_000)],
            [f"name{i}" for i in range(16_000)],
            lambda items: pydoc.html.multicolumn(items, str),
        )

        assert ratio > 24, f"8x the items cost x{ratio:.1f}; linear is x8, quadratic x64"


class TestGetdocWithoutADocstring:
    """`getdoc()` falls back to the comments above an object's source: the
    file goes into linecache once, and on 3.10-3.12 each class costs a parse
    of its whole file."""

    def count_parses(
        self, monkeypatch: pytest.MonkeyPatch, source_dir: pathlib.Path, docstring: bool
    ) -> int:
        name = "documented" if docstring else "undocumented"
        body = '    """A class."""\n' if docstring else "    x = 1\n"
        (source_dir / f"{name}.py").write_text(
            "".join(f"class C{i}:\n{body}\n" for i in range(30)), encoding="utf-8"
        )
        module = __import__(name)
        parses = 0
        original = ast.parse

        def counting(source: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal parses
            if "class C29" in str(source):  # the whole file, not a signature string
                parses += 1
            return original(source, *args, **kwargs)

        monkeypatch.setattr(ast, "parse", counting)
        PLAINTEXT.document(module)
        monkeypatch.setattr(ast, "parse", original)
        return parses

    def test_each_undocumented_class_parses_the_file_before_313(
        self, monkeypatch: pytest.MonkeyPatch, source_dir: pathlib.Path
    ) -> None:
        parses = self.count_parses(monkeypatch, source_dir, docstring=False)

        assert parses == (30 if sys.version_info < (3, 13) else 0)

    def test_documented_classes_never_parse_it(
        self, monkeypatch: pytest.MonkeyPatch, source_dir: pathlib.Path
    ) -> None:
        assert self.count_parses(monkeypatch, source_dir, docstring=True) == 0

    def test_the_source_is_read_into_linecache_once(
        self, monkeypatch: pytest.MonkeyPatch, source_dir: pathlib.Path
    ) -> None:
        (source_dir / "plainfuncs.py").write_text(
            "# First.\ndef one():\n    pass\n\n# Second.\ndef two():\n    pass\n", encoding="utf-8"
        )
        module: Any = __import__("plainfuncs")
        reads = 0
        original = linecache.updatecache

        def counting(*args: Any, **kwargs: Any) -> Any:
            nonlocal reads
            reads += 1
            return original(*args, **kwargs)

        linecache.clearcache()
        monkeypatch.setattr(linecache, "updatecache", counting)

        assert pydoc.getdoc(module.one) == "# First."
        assert pydoc.getdoc(module.two) == "# Second."
        assert reads == 1


class TestNamingAnObjectImportsIt:
    """`locate()` imports each dotted prefix that is a module; `resolve()`
    of an object imports nothing; imports are kept, except with `forceload`."""

    def test_locate_tries_each_prefix_until_one_is_not_a_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json.decoder

        tried: list[str] = []
        original = pydoc.safeimport

        def recording(path: str, *args: Any, **kwargs: Any) -> Any:
            tried.append(path)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(pydoc, "safeimport", recording)

        found = pydoc.locate("json.decoder.JSONDecoder.decode")

        assert found is json.decoder.JSONDecoder.decode
        assert tried == ["json", "json.decoder", "json.decoder.JSONDecoder"]

    def test_an_unknown_name_locates_nothing(self) -> None:
        assert pydoc.locate("json.no_such_name") is None
        with pytest.raises(ImportError, match="No Python documentation found"):
            pydoc.resolve("no_such_module_anywhere_here")

    def test_resolving_an_object_imports_nothing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pydoc, "safeimport", pytest.fail)

        assert pydoc.resolve(len) == (len, "len")

    def test_the_import_runs_once_and_forceload_runs_it_again(
        self, source_dir: pathlib.Path
    ) -> None:
        log = logging_module(source_dir, "noisy")

        pydoc.render_doc("noisy")
        pydoc.render_doc("noisy")
        assert runs(log) == 1

        pydoc.render_doc("noisy", forceload=True)
        assert runs(log) == 2

    def test_forceload_drops_imported_submodules(self, source_dir: pathlib.Path) -> None:
        package = source_dir / "parcel"
        package.mkdir()
        (package / "__init__.py").write_text('"""A parcel."""\n', encoding="utf-8")
        (package / "inner.py").write_text('"""Inner."""\n', encoding="utf-8")
        __import__("parcel.inner")

        pydoc.safeimport("parcel", forceload=True)

        assert "parcel" in sys.modules
        assert "parcel.inner" not in sys.modules

    def test_forceload_leaves_a_built_in_module_in_place(self) -> None:
        assert pydoc.safeimport("sys", forceload=True) is sys
        assert sys.modules["sys"] is sys

    def test_safeimport_returns_none_or_wraps_the_failure(self, source_dir: pathlib.Path) -> None:
        (source_dir / "broken.py").write_text("raise ValueError('boom')\n", encoding="utf-8")

        assert pydoc.safeimport("no_such_module_anywhere_here") is None
        with pytest.raises(pydoc.ErrorDuringImport, match="no_such_parent_here"):
            pydoc.safeimport("no_such_parent_here.child")
        with pytest.raises(pydoc.ErrorDuringImport) as caught:
            pydoc.safeimport("broken")

        assert "problem in" in str(caught.value)
        assert "ValueError: boom" in str(caught.value)

    def test_importfile_runs_the_file_on_every_call(self, source_dir: pathlib.Path) -> None:
        log = logging_module(source_dir, "byfile")

        first = pydoc.importfile(str(source_dir / "byfile.py"))
        second = pydoc.importfile(str(source_dir / "byfile.py"))

        assert runs(log) == 2
        assert first is not second
        assert sys.modules["byfile"] is second

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the exception form is 3.12+")
    def test_error_during_import_takes_the_exception(self) -> None:
        error = ValueError("boom")

        wrapped = pydoc.ErrorDuringImport("f.py", error)  # type: ignore[arg-type]

        assert str(wrapped) == "problem in f.py - ValueError: boom"
        with pytest.warns(DeprecationWarning, match="tuple value"):
            pydoc.ErrorDuringImport("f.py", (ValueError, error, None))  # type: ignore[arg-type]


class TestWritingHtmlFiles:
    """`writedoc()` writes `<name>.html` to the current directory;
    `writedocs()` needs the directory importable from `sys.path`."""

    def test_writedoc_writes_into_the_current_directory(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)

        pydoc.writedoc("json")

        assert (tmp_path / "json.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html")
        assert "wrote json.html" in capsys.readouterr().out

    def make_package(self, root: pathlib.Path) -> pathlib.Path:
        source = root / "tree"
        (source / "shapes").mkdir(parents=True)
        (source / "shapes" / "__init__.py").write_text('"""Shapes."""\n', encoding="utf-8")
        (source / "shapes" / "circle.py").write_text('"""Circles."""\n', encoding="utf-8")
        (source / "lone.py").write_text('"""Alone."""\n', encoding="utf-8")
        return source

    def test_writedocs_documents_every_module_under_the_directory(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        source = self.make_package(tmp_path)
        target = tmp_path / "out"
        target.mkdir()
        monkeypatch.chdir(target)
        monkeypatch.syspath_prepend(str(source))
        before = set(sys.modules)
        try:
            pydoc.writedocs(str(source))
            imported = set(sys.modules) - before
        finally:
            for name in set(sys.modules) - before:
                del sys.modules[name]

        assert sorted(os.listdir(target)) == ["lone.html", "shapes.circle.html", "shapes.html"]
        assert {"lone", "shapes", "shapes.circle"} <= imported
        assert "wrote shapes.circle.html" in capsys.readouterr().out

    def test_writedocs_off_sys_path_finds_nothing(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        source = self.make_package(tmp_path)
        monkeypatch.chdir(tmp_path)

        if sys.version_info >= (3, 11):
            with pytest.raises(ImportError, match="No Python documentation found"):
                pydoc.writedocs(str(source))
        else:
            pydoc.writedocs(str(source))
            assert "No Python documentation found" in capsys.readouterr().out
        assert not list(tmp_path.glob("*.html"))

    def test_doc_reports_an_unknown_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        output = io.StringIO()

        pydoc.doc("no_such_module_anywhere_here", output=output)

        reported = output.getvalue() if sys.version_info >= (3, 11) else capsys.readouterr().out
        assert "No Python documentation found" in reported


class TestRenderers:
    """`render_doc()` and the `text`, `plaintext` and `html` instances."""

    def test_render_doc_defaults_to_overstrike(self) -> None:
        import json

        rich = pydoc.render_doc(json.dumps)
        plain = pydoc.render_doc(json.dumps, renderer=PLAINTEXT)

        assert "d\bdu\bum\bmp\bps\bs" in rich
        assert pydoc.plain(rich) == plain
        assert plain.startswith("Python Library Documentation: function dumps in module json")

    def test_doc_with_output_writes_plain_text_and_starts_no_pager(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pydoc, "pager", pytest.fail)
        output = io.StringIO()

        pydoc.doc(len, output=output)

        assert output.getvalue().startswith("Python Library Documentation: built-in function len")
        assert "\b" not in output.getvalue()

    def test_bold_triples_the_text_and_plaintext_leaves_it(self) -> None:
        assert pydoc.text.bold("abc") == "a\bab\bbc\bc"
        assert PLAINTEXT.bold("abc") == "abc"

    def test_an_instance_is_documented_through_its_class(self) -> None:
        text = pydoc.render_doc(collections.OrderedDict(), renderer=PLAINTEXT)

        assert "OrderedDict object" in text.splitlines()[0]
        assert "class OrderedDict(builtins.dict)" in text

    def test_the_base_class_documents_nothing(self) -> None:
        with pytest.raises(TypeError, match="don't know how to document"):
            pydoc.Doc().document(5)

    def test_getdocloc_links_only_the_standard_library(
        self, source_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        (source_dir / "mine.py").write_text('"""Mine."""\n', encoding="utf-8")

        monkeypatch.delenv("PYTHONDOCS", raising=False)
        assert "docs.python.org" in str(pydoc.text.getdocloc(json))
        assert pydoc.text.getdocloc(__import__("mine")) is None

        monkeypatch.setenv("PYTHONDOCS", "https://example.org/docs")
        assert str(pydoc.text.getdocloc(json)).startswith("https://example.org/docs/")

    def test_html_markup_links_peps_rfcs_urls_and_known_names(self) -> None:
        marked = pydoc.html.markup(
            "See PEP 8, RFC 2822 and https://example.com; call helper().",
            funcs={"helper": "#-helper"},
        )

        assert re.search(r'<a href="[^"]*pep-0008/">PEP 8</a>', marked)
        assert re.search(r'<a href="[^"]*rfc2822\.txt">RFC 2822</a>', marked)
        assert '<a href="https://example.com">' in marked
        assert '<a href="#-helper">helper</a>' in marked

    def test_html_helpers_wrap_what_they_are_given(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "alpha.py").write_text("", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("", encoding="utf-8")
        (tmp_path / "bundle").mkdir()
        (tmp_path / "bundle" / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "loose").mkdir()
        (tmp_path / "loose" / "data.txt").write_text("", encoding="utf-8")

        index = pydoc.html.index(str(tmp_path))

        assert "alpha" in index and "notes" not in index
        assert "<strong>bundle</strong>&nbsp;(package)" in index  # its directory was listed
        assert "loose" not in index
        assert pydoc.html.escape("<a & b>") == "&lt;a &amp; b&gt;"
        assert pydoc.html.multicolumn(["x", "y"], str.upper).count("<br>") == 2
        assert pydoc.html.page("T", "MARKER").count("MARKER") == 1
        assert pydoc.html.preformat("a\nb").count("<br>") == 1
        assert len(PLAINTEXT.formatvalue("x" * 10_000)) <= 103

    def test_a_package_lists_its_directory_without_importing_it(
        self, source_dir: pathlib.Path
    ) -> None:
        package = source_dir / "crate"
        package.mkdir()
        (package / "__init__.py").write_text('"""A crate."""\n', encoding="utf-8")
        (package / "slat.py").write_text("raise RuntimeError('imported')\n", encoding="utf-8")

        text = PLAINTEXT.document(__import__("crate"))

        assert "PACKAGE CONTENTS" in text
        assert "slat" in text
        assert "crate.slat" not in sys.modules


class TestReprsAreCapped:
    """`repr_string()` slices before it calls `repr()`; other types the
    reprlib dispatch does not know are rendered in full and then cut."""

    def test_limits(self) -> None:
        for repr_class in (pydoc.TextRepr, pydoc.HTMLRepr):
            limits = repr_class()
            assert (limits.maxlist, limits.maxtuple, limits.maxdict) == (20, 20, 10)
            assert (limits.maxstring, limits.maxother) == (100, 100)

    def test_the_other_limits_are_reprlib_s(self) -> None:
        defaults = reprlib.Repr()
        for name in ("maxarray", "maxdeque", "maxset", "maxfrozenset", "maxlong", "maxlevel"):
            assert getattr(pydoc.TextRepr(), name) == getattr(defaults, name)
            assert getattr(pydoc.HTMLRepr(), name) == getattr(defaults, name)
        assert issubclass(pydoc.TextRepr, reprlib.Repr)
        assert issubclass(pydoc.HTMLRepr, reprlib.Repr)

    def test_a_long_string_is_cut_before_its_repr_is_built(self) -> None:
        text = "x" * 10_000_000
        renderer = pydoc.TextRepr()

        peak = peak_bytes(lambda: renderer.repr_string(text, 1))

        assert len(renderer.repr_string(text, 1)) <= 102
        assert peak < 10_000, f"repr_string of 10M characters peaked at {peak} bytes"

    def test_an_unhandled_type_is_rendered_in_full_first(self) -> None:
        data = b"x" * 1_000_000
        renderer = pydoc.TextRepr()

        peak = peak_bytes(lambda: renderer.repr1(data, 1))

        assert len(renderer.repr1(data, 1)) <= 100
        assert peak > 1_000_000, f"repr1 of 1 MB of bytes peaked at {peak} bytes"

    def test_a_value_shown_in_a_module_is_cut(self) -> None:
        module = types.ModuleType("valued")
        module.big = list(range(1_000))  # type: ignore[attr-defined]

        text = PLAINTEXT.document(module)

        assert "big = [0, 1, 2" in text
        assert "999" not in text


class TestHelpers:
    """The module-level helpers' results, and the bounds that rest on them."""

    def test_describe(self) -> None:
        import json

        assert pydoc.describe(json) == "package json"
        assert pydoc.describe(json.dumps) == "function dumps"
        assert pydoc.describe(len) == "built-in function len"

    def test_splitdoc(self) -> None:
        assert pydoc.splitdoc("One.\n\nRest.") == ("One.", "Rest.")
        assert pydoc.splitdoc("One.\nTwo.") == ("", "One.\nTwo.")

    def test_cram_keeps_head_and_tail(self) -> None:
        crammed = pydoc.cram("abcdefghijklmnopqrstuvwxyz", 10)

        assert crammed == "abc...wxyz"
        assert pydoc.cram("short", 10) == "short"

    def test_stripid_replace_isdata_and_ispath(self) -> None:
        assert pydoc.stripid("<object at 0xdeadbeef>") == "<object>"
        assert pydoc.replace("a-b_c", "-", "+", "_", "=") == "a+b=c"
        assert pydoc.isdata(5) and not pydoc.isdata(len)
        assert pydoc.ispath(f"a{os.sep}b") and not pydoc.ispath("a.b")

    def test_classname_and_parentname(self) -> None:
        import json.decoder

        decoder = json.decoder.JSONDecoder
        assert pydoc.classname(decoder, "elsewhere") == "json.decoder.JSONDecoder"
        assert pydoc.classname(decoder, "json.decoder") == "JSONDecoder"
        parentname = getattr(pydoc, "parentname", None)
        if parentname is not None:
            assert parentname(decoder.decode, "json.decoder") == "JSONDecoder"
            assert parentname(decoder.decode, "elsewhere") == "json.decoder.JSONDecoder"

    @pytest.mark.skipif(
        sys.version_info < (3, 11, 9) or (3, 12) <= sys.version_info < (3, 12, 3),
        reason="parentname arrived in 3.11.9 and 3.12.3",
    )
    def test_parentname_exists(self) -> None:
        assert callable(getattr(pydoc, "parentname", None))

    def test_visiblename(self) -> None:
        assert pydoc.visiblename("public")
        assert not pydoc.visiblename("_private")
        assert pydoc.visiblename("__len__")
        assert not pydoc.visiblename("__doc__")
        assert not pydoc.visiblename("public", all=["other"])

    def test_sort_attributes_puts_namedtuple_fields_first(self) -> None:
        point = collections.namedtuple("point", ["y", "x"])
        attrs = [(name, "data", point, None) for name in ("count", "x", "y")]

        SORT_ATTRIBUTES(attrs, point)

        assert [name for name, *_ in attrs] == ["y", "x", "count"]

    def test_classify_class_attrs_relabels_descriptors(self) -> None:
        class Sample:
            @property
            def size(self) -> int:
                return 0

            @staticmethod
            def build() -> None:
                pass

        kinds = {name: kind for name, kind, _, _ in pydoc.classify_class_attrs(Sample)}

        assert kinds["size"] == "readonly property"
        assert kinds["build"] == "static method"

    def test_allmethods_walks_a_shared_base_once_per_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Top:
            def shared(self) -> None:
                pass

        class Left(Top):
            pass

        class Right(Top):
            pass

        class Bottom(Left, Right):
            pass

        visits: list[str] = []
        original = pydoc.allmethods

        def recording(cl: Any) -> Any:
            visits.append(cl.__name__)
            return original(cl)

        monkeypatch.setattr(pydoc, "allmethods", recording)

        methods = pydoc.allmethods(Bottom)

        assert visits.count("Top") == 2
        assert visits.count("object") == 2
        assert methods["shared"] is Bottom.shared

    def test_ispackage(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "__init__.py").write_text("", encoding="utf-8")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = pydoc.ispackage(str(tmp_path))

        assert result is True
        deprecated = any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert deprecated == (sys.version_info >= (3, 13))

    def test_pathdirs_keeps_existing_directories_once(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = tmp_path / "missing"
        monkeypatch.setattr(sys, "path", [str(tmp_path), str(tmp_path), str(missing)])

        assert pydoc.pathdirs() == [str(tmp_path)]


class TestSearchingModules:
    """`ModuleScanner.run()` visits every module on `sys.path`, importing
    every package; with a key it reads every source module whole and imports
    every built-in module. `synopsis()` reads the head and caches it."""

    @pytest.fixture
    def scan_root(self, source_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
        kit = source_dir / "kit"
        kit.mkdir()
        (kit / "__init__.py").write_text('"""A kit of tools."""\n', encoding="utf-8")
        (kit / "tools.py").write_text('"""Tools."""\n', encoding="utf-8")
        (source_dir / "geometry.py").write_text(
            '"""Area HELPERS."""\n' + "#" * 200_000 + "\n", encoding="utf-8"
        )
        monkeypatch.setattr(sys, "path", [str(source_dir)])
        monkeypatch.setattr(sys, "builtin_module_names", ())
        return source_dir

    def test_without_a_key_packages_are_imported_and_modules_are_not(
        self, scan_root: pathlib.Path
    ) -> None:
        found: list[str] = []

        pydoc.ModuleScanner().run(lambda path, name, desc: found.append(name))

        assert set(found) == {"geometry", "kit", "kit.tools"}
        assert "kit" in sys.modules
        assert "kit.tools" not in sys.modules
        assert "geometry" not in sys.modules

    def test_with_a_key_each_source_is_read_whole(
        self, scan_root: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lengths: dict[str, list[int]] = collections.defaultdict(list)
        original = pydoc.source_synopsis

        def recording(file: Any) -> Any:
            source = file.getvalue()
            lengths[source.splitlines()[0]].append(len(source))
            return original(file)

        monkeypatch.setattr(pydoc, "source_synopsis", recording)
        found: list[tuple[str, str]] = []

        for _ in range(2):
            pydoc.ModuleScanner().run(
                lambda path, name, desc: found.append((name, desc)), key="area"
            )

        assert found == [("geometry", "Area HELPERS.")] * 2
        whole = len((scan_root / "geometry.py").read_text(encoding="utf-8"))
        assert lengths['"""Area HELPERS."""'] == [whole, whole], "each search reads it again"

    def test_the_server_search_is_the_same_scan(self, scan_root: pathlib.Path) -> None:
        handler = pydoc._url_handler  # type: ignore[attr-defined]  # the server's own handler

        page = handler("search?key=helpers", "text/html")

        assert "geometry" in page
        assert "Area&nbsp;HELPERS." in page or "Area HELPERS." in page

    def test_setting_quit_stops_the_walk(self, scan_root: pathlib.Path) -> None:
        scanner = pydoc.ModuleScanner()
        found: list[str] = []

        def stop_after_one(path: Any, name: str, desc: str) -> None:
            found.append(name)
            scanner.quit = True

        scanner.run(stop_after_one)

        assert len(found) == 1

    def test_apropos_prints_matches_ignoring_case(
        self, scan_root: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pydoc.apropos("helpers")

        assert capsys.readouterr().out == "geometry - Area HELPERS.\n"

    def test_listmodules_with_a_key_prints_past_the_helper_output(
        self, scan_root: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output = io.StringIO()

        pydoc.Helper(output=output).listmodules("helpers")

        assert "geometry - Area HELPERS." in capsys.readouterr().out
        assert "geometry" not in output.getvalue()

    def test_listmodules_without_a_key_lists_top_level_names(self, scan_root: pathlib.Path) -> None:
        output = io.StringIO()

        pydoc.Helper(output=output).listmodules()

        listed = output.getvalue()
        assert "geometry" in listed and "kit" in listed
        assert "kit.tools" not in listed
        assert "kit" in sys.modules

    def test_a_keyed_scan_imports_every_built_in_module(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import pkgutil
            import sys
            import pydoc

            import builtins

            pkgutil.walk_packages = lambda *args, **kwargs: iter(())
            names = {n for n in sys.builtin_module_names if n != '__main__'}
            original = builtins.__import__
            asked = set()

            def recording(name, *args, **kwargs):
                asked.add(name)
                return original(name, *args, **kwargs)

            builtins.__import__ = recording
            pydoc.ModuleScanner().run(lambda *args: None)
            print(len(names & asked))
            asked.clear()
            pydoc.ModuleScanner().run(lambda *args: None, key='zzzz')
            print(len(names - asked))
            """,
            tmp_path,
        )

        assert result.returncode == 0, result.stderr
        unkeyed, missed = map(int, result.stdout.split())
        assert unkeyed == 0, "an unkeyed scan imported built-in modules"
        assert missed == 0, "a keyed scan skipped built-in modules"

    def test_quit_does_not_stop_the_built_in_loop(
        self, scan_root: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "builtin_module_names", ("sys", "math"))
        scanner = pydoc.ModuleScanner()
        found: list[str] = []

        def stop_at_once(path: Any, name: str, desc: str) -> None:
            found.append(name)
            scanner.quit = True

        scanner.run(stop_at_once)

        assert found == ["sys", "math"]

    def test_synopsis_is_cached_until_the_file_changes(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "summary.py"
        path.write_text('"""First summary."""\n', encoding="utf-8")
        opens = 0
        original = tokenize.open

        def counting(*args: Any) -> Any:
            nonlocal opens
            opens += 1
            return original(*args)

        monkeypatch.setattr(tokenize, "open", counting)

        assert pydoc.synopsis(str(path)) == "First summary."
        assert pydoc.synopsis(str(path)) == "First summary."
        assert opens == 1

        path.write_text('"""Second summary."""\n', encoding="utf-8")
        later = path.stat().st_mtime + 10
        os.utime(path, (later, later))

        assert pydoc.synopsis(str(path)) == "Second summary."
        assert opens == 2

        path.write_text('"""Third summary."""\n', encoding="utf-8")
        earlier = later - 100
        os.utime(path, (earlier, earlier))

        assert pydoc.synopsis(str(path)) == "Second summary.", "an older mtime keeps the cache"
        assert opens == 2

    def test_synopsis_of_compiled_code_runs_it(self, tmp_path: pathlib.Path) -> None:
        log = logging_module(tmp_path, "compiled")
        compiled = tmp_path / "compiled.pyc"
        py_compile.compile(str(tmp_path / "compiled.py"), cfile=str(compiled), doraise=True)

        assert pydoc.synopsis(str(compiled)) == "Logs every run."
        assert pydoc.synopsis(str(compiled)) == "Logs every run."
        assert runs(log) == 1, "the cached answer does not run it again"
        assert "__temp__" not in sys.modules

    def test_source_synopsis_reads_only_the_head(self) -> None:
        class CountingLines(io.StringIO):
            reads = 0

            def readline(self, size: int = -1) -> str:
                CountingLines.reads += 1
                return super().readline(size)

        source = CountingLines('"""Head line."""\n' + "x = 1\n" * 10_000)

        assert pydoc.source_synopsis(source) == "Head line."
        assert CountingLines.reads <= 5

        CountingLines.reads = 0
        assert pydoc.source_synopsis(CountingLines("x = 1\n" * 10_000)) is None
        assert CountingLines.reads <= 5, "a file without a docstring stops at its first statement"


class TestTheHelper:
    """`Helper(input, output)` answers through its streams; topic texts reach
    `output` from 3.12.5; `interact()` stops at `q`."""

    def test_keywords_and_objects_go_to_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pydoc, "pager", pytest.fail)
        output = io.StringIO()
        helper = pydoc.Helper(output=output)

        helper.help("keywords")
        helper.help(len)

        assert "nonlocal" in output.getvalue()
        assert "Help on built-in function len in module builtins" in output.getvalue()

    def test_topic_text_goes_to_output_from_3_12_5(self, monkeypatch: pytest.MonkeyPatch) -> None:
        paged: list[str] = []
        monkeypatch.setattr(pydoc, "pager", lambda text, title="": paged.append(text))
        output = io.StringIO()

        pydoc.Helper(output=output).help("with")

        if sys.version_info >= (3, 12, 5):
            assert "with" in output.getvalue() and not paged
        else:
            assert paged and "with" in paged[0]

    def test_the_streams_default_to_sys_at_each_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        helper = pydoc.Helper()
        replacement = io.StringIO()

        monkeypatch.setattr(sys, "stdout", replacement)

        assert helper.output is replacement

    def test_list_sorts_into_columns(self) -> None:
        output = io.StringIO()

        pydoc.Helper(output=output).list(["c", "a", "b", "d"], columns=2, width=10)

        assert output.getvalue().split() == ["a", "c", "b", "d"]

    def test_the_tables_are_fixed_and_small(self) -> None:
        for table in (pydoc.Helper.keywords, pydoc.Helper.symbols, pydoc.Helper.topics):
            assert 20 < len(table) < 100

    def test_interact_runs_one_request_per_line_until_q(self) -> None:
        output = io.StringIO()
        helper = pydoc.Helper(input=io.StringIO("keywords\nlen\nq\nnever\n"), output=output)

        helper.interact()

        assert "nonlocal" in output.getvalue()
        assert "built-in function len" in output.getvalue()
        assert "never" not in output.getvalue()

    def test_the_end_of_a_stream_stops_interact_before_3_13_12_and_3_14_3(self) -> None:
        class Scripted(pydoc.Helper):
            calls = 0

            def getline(self, prompt: str) -> str:
                Scripted.calls += 1
                if Scripted.calls > 50:
                    raise EOFError
                return "keywords\n" if Scripted.calls == 1 else ""

        Scripted(input=io.StringIO(), output=io.StringIO()).interact()

        keeps_asking = sys.version_info >= (3, 14, 3) or (3, 13, 12) <= sys.version_info < (3, 14)
        assert Scripted.calls == (51 if keeps_asking else 2)


class TestPagers:
    """`pager()` picks a pager once per process; the plain pager writes to
    `sys.stdout`; the others hand the text to a command or the terminal."""

    def test_the_pager_is_chosen_once(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import pydoc

            name = 'get_pager' if hasattr(pydoc, 'get_pager') else 'getpager'
            original = getattr(pydoc, name)
            calls = []
            setattr(pydoc, name, lambda: calls.append(1) or original())
            for _ in range(3):
                pydoc.pager('b\\bbold\\n')
            print(len(calls), pydoc.pager is pydoc.plainpager)
            """,
            tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == ["bold", "bold", "bold", "1 True"]

    def test_the_pager_names(self, capsys: pytest.CaptureFixture[str]) -> None:
        old = ("getpager", "plainpager", "pipepager", "tempfilepager", "ttypager")
        new = ("get_pager", "plain_pager", "pipe_pager", "tempfile_pager", "tty_pager")

        assert all(hasattr(pydoc, name) for name in old)
        if sys.version_info >= (3, 13):
            assert [getattr(pydoc, n) for n in old] == [getattr(pydoc, n) for n in new]
            pydoc.plainpager("text\n", "a title")
            assert capsys.readouterr().out == "text\n"
        else:
            assert not any(hasattr(pydoc, name) for name in new)

    def test_get_pager_is_plain_off_a_terminal(self, capsys: pytest.CaptureFixture[str]) -> None:
        chooser = getattr(pydoc, "get_pager", None) or pydoc.getpager

        assert chooser() is pydoc.plainpager

    def test_plain_pager_writes_plain_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        pydoc.plainpager("b\bbold\n")

        assert capsys.readouterr().out == "bold\n"

    def test_pipe_pager_feeds_a_command(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "piped.txt"
        copy = "import sys; open(sys.argv[1], 'w').write(sys.stdin.read())"

        pydoc.pipepager("piped text\n", shell_command(sys.executable, "-c", copy, str(target)))

        assert target.read_text() == "piped text\n"

    def test_tempfile_pager_runs_a_command_on_a_file(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "copied.txt"
        copy = "import shutil, sys; shutil.copyfile(sys.argv[2], sys.argv[1])"

        pydoc.tempfilepager("file text\n", shell_command(sys.executable, "-c", copy, str(target)))

        assert target.read_text() == "file text\n"

    def test_tty_pager_shows_a_screenful_then_waits(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("LINES", "5")
        monkeypatch.setattr(sys, "stdin", io.StringIO("q\n"))

        pydoc.ttypager("".join(f"line {i}\n" for i in range(100)))

        shown = capsys.readouterr().out
        assert "line 3" in shown and "line 4" not in shown
        assert "-- more --" in shown


class TestTheServer:
    """Each page is rendered on request, a module page imports its module
    again, and the server handles one request at a time."""

    def test_every_module_page_runs_the_module_again(self, source_dir: pathlib.Path) -> None:
        log = logging_module(source_dir, "served")
        handler = pydoc._url_handler  # type: ignore[attr-defined]  # the server's own handler

        first = handler("served.html", "text/html")
        second = handler("get?key=served", "text/html")

        assert "<title>Pydoc: module served</title>" in first
        assert "<title>Pydoc: module served</title>" in second
        assert runs(log) == 2

    def test_the_server_is_single_threaded_and_serves_pages(self, source_dir: pathlib.Path) -> None:
        # A module page re-imports its module in this process, so serve a
        # throwaway module rather than one other tests hold references into.
        logging_module(source_dir, "servedbythread")
        start = pydoc._start_server  # type: ignore[attr-defined]
        thread = start(pydoc._url_handler, "localhost", 0)  # type: ignore[attr-defined]
        try:
            assert thread.error is None
            assert not isinstance(thread.docserver, socketserver.ThreadingMixIn)
            url = thread.url + "servedbythread.html"
            with urllib.request.urlopen(url, timeout=30) as response:
                page = response.read().decode("utf-8")
        finally:
            thread.stop()

        assert "<title>Pydoc: module servedbythread</title>" in page

    def test_the_command_line_server_stops_at_q(self, tmp_path: pathlib.Path) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "pydoc", "-p", "0"],
            cwd=tmp_path,
            input="q\n",
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert re.search(r"Server ready at http://localhost:\d+/", result.stdout)
        assert "Server stopped" in result.stdout


class TestTheCommandLine:
    """`python -m pydoc` documents a name, a file by path, or writes HTML."""

    def test_a_path_is_imported_and_run(self, tmp_path: pathlib.Path) -> None:
        tool = tmp_path / "tool.py"
        tool.write_text('"""A small tool."""\nprint("tool ran")\n', encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pydoc", str(tool)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "tool ran" in result.stdout
        assert "A small tool." in result.stdout

    def test_cli_puts_a_missing_current_directory_on_sys_path(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "herenow.py").write_text('"""Here now."""\n', encoding="utf-8")

        result = run_python(
            """
            import os
            import sys
            import pydoc

            sys.path[:] = [p for p in sys.path if p not in ('', os.curdir, os.getcwd())]
            sys.argv = [sys.argv[0], 'herenow']
            pydoc.cli()
            print(sys.path[0] == os.getcwd())
            """,
            tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert "Here now." in result.stdout
        assert result.stdout.rstrip().endswith("True")

    def test_the_current_directory_is_importable_and_w_writes_html(
        self, tmp_path: pathlib.Path
    ) -> None:
        (tmp_path / "localmod.py").write_text('"""Local."""\n', encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pydoc", "-w", "localmod"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "localmod.html").exists()


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
    """Each block runs in its own subprocess and working directory, with no
    terminal on stdin, so no pager or prompt can wait for input; the bash
    block that starts the server is covered by
    `TestTheServer.test_the_command_line_server_stops_at_q`."""

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
            if result.returncode != 0 or result.stdout:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}{result.stdout}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "count('run') == 2" in s)
        mutated = source.replace("count('run') == 2", "count('run') == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
