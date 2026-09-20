"""Tests for docs/builtins/__import__.md.

The page prices the builtin as a `sys.modules` probe in front of a search, and
prices the `import` statement as one `IMPORT_NAME` per module named, each
calling whatever `__import__` the executing frame's builtins hold. Every row is settled by
observation rather than a stopwatch: a recording meta path finder says whether
a search happened, a package with a counting module-level `__getattr__` says
how many attribute checks a `fromlist` made, a sentinel list says which module
bodies ran and in what order, and a recording replacement in
`builtins.__import__` says what the statement passed and how often.

Measurement scope:

* A module already in `sys.modules` is returned as the same object with the
  recording finder untouched; a name that is nowhere reaches that finder
  exactly once. A `None` entry raises `ModuleNotFoundError` naming
  `sys.modules` rather than being returned. A module whose body is still
  running in another thread is waited for: a second thread that has reached
  its call has not returned 0.3 s after the body started, and returns once the
  body is released. The waiting thread signals before it calls and timestamps
  its return, and the test asserts that return came after the release. That is
  consistent with the call blocking, not proof of it: the thread can be
  descheduled between its signal and the call, or between the call returning
  and the timestamp, so blocking itself stays incompletely settled here.
  Dropping the entry runs the body again and yields a different object, and
  `reload()` runs it a third time.
* A three-level dotted package written to a temporary directory runs each
  body once, top down, and the call returns the top-level package. The
  recording finder is asked for each of the three names in that order, and is
  asked nothing when the same call is repeated. A relative call with an empty
  `fromlist` returns the head of `name` under the anchor - `xml.sax` for
  `name="sax.handler"` anchored on `xml` - and not the top-level package,
  consulting no finder to reach it. That rule is asserted for
  `importlib.__import__` as well as the builtin, because the importlib page
  makes the same claim about its own function.
* `fromlist` is counted with a package whose `__init__` defines a
  `__getattr__` that records the name and raises `AttributeError`: two names
  record two checks and import both submodules, and the repeated call records
  none and reaches no finder, because the submodules are attributes by then.
  A name that is neither an attribute nor an importable submodule is searched
  for on both of two identical calls, and leaves no attribute behind.
  A module without `__path__` records the machinery's own `__path__` check and
  no name from the list. `'*'` expands to `__all__`: `xml` imports its four
  submodules, `json` reaches no finder because its `__all__` is functions and
  classes, and a package with no `__all__` records exactly one check, for
  `__all__` itself, and imports nothing.
* `level` is resolved against `globals`: the default `None` raises `TypeError`
  before any finder is consulted, `__spec__.parent` resolves the anchor on its
  own, `__package__` is preferred over a `__spec__.parent` that disagrees (and
  that disagreement raises `DeprecationWarning` from 3.12 and `ImportWarning`
  on 3.10 and 3.11), and globals carrying only `__name__` resolve behind an
  `ImportWarning`. Every one of those globals is supplied by the test rather
  than by a module, which is the page's claim that `level` needs a suitable
  dict and not a particular caller. That it must be a `dict` and not any
  mapping is asserted both ways: a `MappingProxyType` over the same keys is
  refused, and a `dict` subclass is accepted. One dedicated test passes a
  `locals` that raises on any access, at level 0 and at level 1.
* Statement forms are read from `dis` and from a recording replacement in
  `builtins.__import__`: `import pkg.mod` and `import pkg.mod as name` pass a
  falsy `fromlist` and level 0, `from pkg.mod import x, y` passes `('x', 'y')`,
  `from . import x` passes level 1 with an empty name, and `from pkg import *`
  passes `('*',)`. The replacement is uninstalled before each assertion runs,
  because pytest's own lazy imports would otherwise be recorded as well.
  It is called once per statement executed, and the modules a form needs are
  loaded before it is installed so that only the statements under test are
  counted. Deleting the name leaves `import` raising `ImportError`.
  `importlib.__import__` is a distinct object whose own call does not reach the
  entry, while an import statement in a module body it loads does. A frame
  given its own `__builtins__` mapping reaches that mapping's `__import__`
  instead, for the statement and for a bare `__import__(...)` call alike.
* The attribute fallback behind `import pkg.mod as name` and
  `from pkg import mod` is observed by deleting the submodule attribute from a
  temporary package: both still bind the module from `sys.modules`, and the
  counting `__getattr__` records the three misses that took it - the `as`
  form's attribute load, the second statement's `fromlist` check, and its own
  attribute load. The recording finder stays empty throughout, because
  `bpkg.leaf` was in `sys.modules`: an import a `fromlist` triggers for a name
  the package lacks is a probe when that module is loaded, not a search.
* `from pkg import *` binds `__all__` when it is defined and every name not
  starting with `_` when it is not, and binds them again on a second
  execution. A module imported inside a function runs its body on the first
  call that reaches it and not before.

Not settled here:

* The O(t + p·s + e) shape of one search - the meta path walk, the per-entry
  suffix tries, and the directory listing a first search pays - is the
  importlib page's rows. This file asserts only that a miss reaches the meta
  path and that each missing component costs its own search, and does not
  re-measure the per-entry terms; tests/test_importlib_complexity.py covers
  them.
* Pricing one attribute check and one `find_spec()` call as O(1) is the page's
  cost model, not a measurement. A module `__getattr__` or a finder written by
  the caller can cost anything, and the O(f), O(a) and O(t) terms count calls
  rather than bound their contents. The counting `__getattr__` used here is
  itself an example of such a hook.
* `n` and `m` - the bytes read and what a module body itself costs - are not
  varied. The bodies written here are a few lines each, so the per-component
  claim is settled on count and order, not on size.
* That the interpreter reaches the unmodified builtin without a Python-level
  call is read from `_PyEval_ImportName` in Python/ceval.c. Both paths end in
  the same C function, so no observation distinguishes them; only the
  replaced case, where a Python call does happen, is asserted here.
* The 3.10 and 3.11 `ImportWarning` for a `__package__` that disagrees with
  `__spec__.parent` is asserted by a version-gated branch that only CI on
  those interpreters executes.
* An attribute check that *succeeds* is invisible to a module-level
  `__getattr__`, which runs only on failure. What is asserted is one recorded
  check per name the package lacks, and no import when the name is already an
  attribute; the page's "one attribute check per name" is read from
  `_handle_fromlist` in Lib/importlib/_bootstrap.py.
"""

from __future__ import annotations

import builtins
import dis
import importlib
import pathlib
import re
import subprocess
import sys
import sysconfig
import textwrap
import threading
import time
import types
from collections.abc import Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "__import__.md"
EXPECTED_BLOCKS = 9


@pytest.fixture(autouse=True)
def import_state() -> Iterator[None]:
    """Restore the import system's shared state after every test."""
    path = list(sys.path)
    meta_path = list(sys.meta_path)
    modules = set(sys.modules)
    original_import = builtins.__import__
    yield
    builtins.__import__ = original_import
    sys.path[:] = path
    sys.meta_path[:] = meta_path
    stdlib = sysconfig.get_paths()["stdlib"]
    for name in set(sys.modules) - modules:
        origin = getattr(getattr(sys.modules[name], "__spec__", None), "origin", None)
        if origin is None or not str(origin).startswith(stdlib):
            del sys.modules[name]
    importlib.invalidate_caches()
    sys.path_importer_cache.clear()


class Recorder:
    """A meta path finder that answers nothing and records what it was asked."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> None:
        self.asked.append(fullname)
        return None


class Recording:
    """A replacement for `builtins.__import__` that records what it was passed.

    It is installed by `start()` rather than on construction, because a cold
    module's own body imports through the replacement too and would be counted;
    and it must be uninstalled before the assertions run, because pytest imports
    its own modules lazily while rewriting an assertion.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.original = builtins.__import__

    def start(self) -> Recording:
        """Install only once the caller has imported what it does not want recorded."""
        builtins.__import__ = self
        return self

    def __call__(
        self,
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        self.calls.append((name, fromlist, level))
        return self.original(name, globals, locals, fromlist, level)

    def stop(self) -> list[tuple[Any, ...]]:
        builtins.__import__ = self.original
        return list(self.calls)


class Hostile:
    """A mapping that fails on any access, used where the page says nothing reads it."""

    def __getitem__(self, key: str) -> Any:
        raise AssertionError(f"the mapping was read for {key!r}")

    def keys(self) -> Any:
        raise AssertionError("the mapping was enumerated")


def write_module(directory: pathlib.Path, name: str, source: str) -> pathlib.Path:
    path = directory / f"{name}.py"
    path.write_text(source, encoding="utf-8")
    return path


def counting_package(root: pathlib.Path, name: str, submodules: tuple[str, ...]) -> list[str]:
    """A package whose failed attribute lookups append to the returned list."""
    package = root / name
    package.mkdir()
    write_module(
        package,
        "__init__",
        "CHECKS = []\n"
        "def __getattr__(name):\n"
        "    CHECKS.append(name)\n"
        "    raise AttributeError(name)\n",
    )
    for index, submodule in enumerate(submodules):
        write_module(package, submodule, f"VALUE = {index}\n")
    sys.path.insert(0, str(root))
    return []


def sentinel(name: str) -> types.ModuleType:
    """A module the written bodies append their own names to."""
    module = types.ModuleType(name)
    module.RUNS = []  # type: ignore[attr-defined]
    sys.modules[name] = module
    return module


class TestALoadedModuleIsAProbe:
    """`__import__(name)` with `name` in `sys.modules` | O(1) | O(1): one dict
    probe, and no finder is consulted.

    A recording meta path finder separates the probe, which reaches nothing,
    from a miss, which reaches it.
    """

    def test_a_loaded_module_is_the_same_object_and_reaches_no_finder(self) -> None:
        import base64

        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        assert __import__("base64") is base64
        assert __import__("base64") is sys.modules["base64"]
        assert recorder.asked == []

    def test_a_missing_name_reaches_the_meta_path_once(self) -> None:
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        with pytest.raises(ModuleNotFoundError) as info:
            __import__("no_such_module_anywhere")

        assert info.value.name == "no_such_module_anywhere"
        assert recorder.asked == ["no_such_module_anywhere"]

    def test_a_none_entry_raises_instead_of_searching(self) -> None:
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)
        sys.modules["blocked_module"] = None  # type: ignore[assignment]

        with pytest.raises(ModuleNotFoundError) as info:
            __import__("blocked_module")

        assert "None in sys.modules" in str(info.value)
        assert recorder.asked == []

    def test_dropping_the_entry_or_reloading_runs_the_body_again(
        self, tmp_path: pathlib.Path
    ) -> None:
        runs = sentinel("rerun_sentinel")
        write_module(
            tmp_path,
            "rerun",
            "import rerun_sentinel\nrerun_sentinel.RUNS.append('rerun')\n",
        )
        sys.path.insert(0, str(tmp_path))

        first = __import__("rerun")
        assert runs.RUNS == ["rerun"]  # type: ignore[attr-defined]
        assert __import__("rerun") is first  # the probe answers, the body does not run
        assert runs.RUNS == ["rerun"]  # type: ignore[attr-defined]

        del sys.modules["rerun"]
        second = __import__("rerun")
        assert second is not first
        assert runs.RUNS == ["rerun", "rerun"]  # type: ignore[attr-defined]

        importlib.reload(second)
        assert runs.RUNS == ["rerun", "rerun", "rerun"]  # type: ignore[attr-defined]

    def test_a_module_another_thread_is_running_is_waited_for(self, tmp_path: pathlib.Path) -> None:
        gate = sentinel("import_gate")
        gate.started = threading.Event()  # type: ignore[attr-defined]
        gate.release = threading.Event()  # type: ignore[attr-defined]
        write_module(
            tmp_path,
            "slow_body",
            "import import_gate\n"
            "import_gate.started.set()\n"
            "assert import_gate.release.wait(10)\n"
            "VALUE = 1\n",
        )
        sys.path.insert(0, str(tmp_path))

        first = threading.Thread(target=__import__, args=("slow_body",), daemon=True)
        first.start()
        assert gate.started.wait(10)  # type: ignore[attr-defined]

        second_entered = threading.Event()
        second_returned = threading.Event()
        returned_at: list[float] = []

        def second_import() -> None:
            second_entered.set()
            __import__("slow_body")
            returned_at.append(time.monotonic())
            second_returned.set()

        second = threading.Thread(target=second_import, daemon=True)
        second.start()
        assert second_entered.wait(10)
        try:
            assert not second_returned.wait(0.3)
        finally:
            # Before the release, not after: a main thread descheduled in
            # between would otherwise time the release after the return.
            released_at = time.monotonic()
            gate.release.set()  # type: ignore[attr-defined]
        assert second_returned.wait(10)
        first.join(10)
        second.join(10)

        # Consistent with waiting rather than proof of it: the thread may be
        # descheduled between its signal and the call, or between the call
        # returning and the timestamp.
        assert returned_at and returned_at[0] > released_at
        assert sys.modules["slow_body"].VALUE == 1


class TestAMissCostsOnePerComponent:
    """`__import__(name)` when `name` is not loaded | O(c·(t + p·s) + n + m):
    a find and a load for every missing component of the dotted name, top down.

    The recording finder counts the finds and a sentinel list counts the loads,
    which separates one search for the whole dotted name from one per
    component.
    """

    def test_each_component_is_found_and_run_once_top_down(self, tmp_path: pathlib.Path) -> None:
        runs = sentinel("component_sentinel")
        (tmp_path / "apkg" / "bpkg").mkdir(parents=True)
        packages = ((tmp_path / "apkg", "apkg"), (tmp_path / "apkg" / "bpkg", "apkg.bpkg"))
        for directory, name in packages:
            write_module(
                directory,
                "__init__",
                f"import component_sentinel\ncomponent_sentinel.RUNS.append({name!r})\n",
            )
        write_module(
            tmp_path / "apkg" / "bpkg",
            "leaf",
            "import component_sentinel\ncomponent_sentinel.RUNS.append('leaf')\n",
        )
        sys.path.insert(0, str(tmp_path))
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        top = __import__("apkg.bpkg.leaf")

        assert runs.RUNS == ["apkg", "apkg.bpkg", "leaf"]  # type: ignore[attr-defined]
        assert recorder.asked == ["apkg", "apkg.bpkg", "apkg.bpkg.leaf"]

        recorder.asked.clear()
        assert __import__("apkg.bpkg.leaf") is top
        assert runs.RUNS == ["apkg", "apkg.bpkg", "leaf"]  # type: ignore[attr-defined]
        assert recorder.asked == []


class TestTheReturnValueDependsOnFromlist:
    """Empty `fromlist` returns the top-level package; a non-empty one returns
    the module `name` asks for.

    Identity against `sys.modules` and `import_module()` separates the two,
    which no bound could.
    """

    def test_a_dotted_name_returns_the_top_level_package(self, tmp_path: pathlib.Path) -> None:
        counting_package(tmp_path, "rpkg", ("leaf",))
        __import__("rpkg.leaf")
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        top = __import__("rpkg.leaf")

        assert top.__name__ == "rpkg"
        assert top is sys.modules["rpkg"]
        assert sys.modules["rpkg.leaf"].VALUE == 0
        assert recorder.asked == []  # reaching the top package is a probe, not a search

    def test_a_relative_dotted_name_returns_the_head_under_the_anchor(self) -> None:
        import xml.sax.handler

        anchored = {"__name__": "xml", "__package__": "xml", "__spec__": xml.__spec__}
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        # Not the top-level `xml`: the head of `name`, resolved against the anchor
        assert __import__("sax.handler", anchored, None, (), 1) is xml.sax
        assert recorder.asked == []  # the resolved name was already in sys.modules

    @pytest.mark.parametrize("dunder_import", [__import__, importlib.__import__])
    def test_both_implementations_return_the_same_head(
        self, dunder_import: Any, tmp_path: pathlib.Path
    ) -> None:
        """The importlib page makes this claim about its own function too."""
        import xml.sax.handler

        counting_package(tmp_path, "hpkg", ("leaf",))
        anchored = {"__name__": "xml", "__package__": "xml", "__spec__": xml.__spec__}

        assert dunder_import("hpkg.leaf").__name__ == "hpkg"  # absolute: the top package
        assert dunder_import("sax.handler", anchored, None, (), 1) is xml.sax  # relative: the head
        assert dunder_import("hpkg.leaf", fromlist=["VALUE"]).__name__ == "hpkg.leaf"

    def test_a_fromlist_returns_the_module_named(self, tmp_path: pathlib.Path) -> None:
        counting_package(tmp_path, "rpkg", ("leaf",))

        named = __import__("rpkg.leaf", fromlist=["VALUE"])

        assert named.__name__ == "rpkg.leaf"
        assert named is sys.modules["rpkg.leaf"]
        assert importlib.import_module("rpkg.leaf") is named


class TestFromlistChecksEachName:
    """`fromlist` | O(f): one attribute check per name, and a full import of
    each name the package lacks.

    A module-level `__getattr__` that records and raises counts the checks that
    fail; a second identical call makes the same checks succeed, which
    separates "checked every time" from "imported every time".
    """

    def test_each_name_is_checked_and_only_the_missing_are_imported(
        self, tmp_path: pathlib.Path
    ) -> None:
        counting_package(tmp_path, "fpkg", ("leaf", "other"))
        recorder = Recorder()

        package = __import__("fpkg", fromlist=["leaf", "other"])
        assert package.CHECKS == ["leaf", "other"]
        assert sys.modules["fpkg.leaf"].VALUE == 0
        assert sys.modules["fpkg.other"].VALUE == 1

        package.CHECKS.clear()
        sys.meta_path.insert(0, recorder)
        assert __import__("fpkg", fromlist=["leaf", "other"]) is package
        assert package.CHECKS == []  # both are attributes now, so __getattr__ is not reached
        assert recorder.asked == []  # and nothing was imported

    def test_a_name_that_is_neither_is_searched_for_every_call(
        self, tmp_path: pathlib.Path
    ) -> None:
        counting_package(tmp_path, "gpkg", ())
        package = __import__("gpkg")
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        assert __import__("gpkg", fromlist=["ghost"]) is package
        assert __import__("gpkg", fromlist=["ghost"]) is package

        assert package.CHECKS == ["ghost", "ghost"]
        assert recorder.asked == ["gpkg.ghost", "gpkg.ghost"]  # searched both times
        assert not hasattr(package, "ghost")  # and the failure said nothing

    def test_a_module_without_a_path_checks_no_name(self, tmp_path: pathlib.Path) -> None:
        write_module(
            tmp_path,
            "flat_module",
            "CHECKS = []\n"
            "def __getattr__(name):\n"
            "    CHECKS.append(name)\n"
            "    raise AttributeError(name)\n",
        )
        sys.path.insert(0, str(tmp_path))

        module = __import__("flat_module", fromlist=["no_such_name", "nor_this"])

        assert module.__name__ == "flat_module"
        assert "__path__" in module.CHECKS  # the machinery asks, and stops there
        assert [name for name in module.CHECKS if not name.startswith("__")] == []


class TestStarExpandsToAll:
    """`fromlist=["*"]` | O(a): expands to the package's `__all__` and checks
    those names instead; a package without `__all__` costs nothing.

    Three packages separate the cases: one whose `__all__` is submodules, one
    whose `__all__` is already attributes, and one with no `__all__`.
    """

    def test_submodules_in_all_are_imported(self) -> None:
        package = __import__("xml", fromlist=["*"])

        assert package.__all__ == ["dom", "parsers", "sax", "etree"]
        assert {"xml.dom", "xml.parsers", "xml.sax", "xml.etree"} <= set(sys.modules)

    def test_names_that_are_already_attributes_import_nothing(self) -> None:
        import json

        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        assert __import__("json", fromlist=["*"]) is json
        assert recorder.asked == []

    def test_a_package_without_all_expands_to_nothing(self, tmp_path: pathlib.Path) -> None:
        counting_package(tmp_path, "spkg", ("leaf",))
        package = __import__("spkg")
        assert not hasattr(package, "__all__")

        package.CHECKS.clear()
        assert __import__("spkg", fromlist=["*"]) is package
        assert package.CHECKS == ["__all__"]  # asked once, and there was nothing to expand
        assert "spkg.leaf" not in sys.modules


class TestRelativeImportsReadGlobals:
    """`level=k` | O(1): resolved against `globals` - `__package__`, else
    `__spec__.parent`, else `__name__` behind an `ImportWarning`.

    The recording finder shows the `TypeError` arrives before any search, and
    a deliberately mismatched `__package__` shows which of the two wins.
    """

    def test_the_default_globals_fail_before_any_search(self) -> None:
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        with pytest.raises(TypeError, match="globals must be a dict"):
            __import__("decoder", None, None, ("JSONDecoder",), 1)

        assert recorder.asked == []

    def test_any_mapping_other_than_a_dict_is_refused(self) -> None:
        import json

        anchor = {"__name__": "json", "__package__": "json"}

        with pytest.raises(TypeError, match="globals must be a dict"):
            __import__("decoder", types.MappingProxyType(anchor), None, ("x",), 1)

        class Subclass(dict[str, Any]):
            pass

        # A dict subclass is a dict, so it is accepted
        assert __import__("decoder", Subclass(anchor), None, ("x",), 1) is json.decoder

    def test_package_resolves_the_anchor(self) -> None:
        import json.decoder

        inside = {"__name__": "json", "__package__": "json", "__spec__": json.__spec__}

        assert __import__("decoder", inside, None, ("JSONDecoder",), 1) is json.decoder

    def test_spec_parent_resolves_the_anchor_when_package_is_absent(self) -> None:
        import json.decoder

        spec_only = {"__name__": "not consulted", "__spec__": json.__spec__}

        assert __import__("decoder", spec_only, None, ("JSONDecoder",), 1) is json.decoder

    def test_package_wins_over_a_disagreeing_spec_parent(self) -> None:
        import json

        mismatched = {
            "__name__": "json",
            "__package__": "no_such_package",
            "__spec__": json.__spec__,
        }
        expected = DeprecationWarning if sys.version_info >= (3, 12) else ImportWarning

        with pytest.warns(expected, match=r"__package__ != __spec__\.parent"):
            with pytest.raises(ModuleNotFoundError) as info:
                __import__("decoder", mismatched, None, ("x",), 1)

        assert info.value.name == "no_such_package"  # resolved against __package__, not the spec

    def test_name_is_the_last_resort_and_warns(self) -> None:
        with pytest.warns(ImportWarning, match="falling back on __name__"):
            resolved = __import__("scanner", {"__name__": "json.decoder"}, None, ("x",), 1)

        assert resolved is sys.modules["json.scanner"]

    def test_locals_is_never_read(self) -> None:
        import json

        hostile: Any = Hostile()

        assert __import__("json", hostile, hostile) is json  # level 0 reads neither
        anchored = {"__name__": "json", "__package__": "json"}
        assert __import__("decoder", anchored, hostile, ("JSONDecoder",), 1).__name__ == (
            "json.decoder"
        )


class TestTheStatementCallsTheBuiltin:
    """`builtins.__import__` | O(1): `IMPORT_NAME` reads it from the frame's
    builtins every time, so a replacement takes effect at once and is called
    again on every subsequent import statement.

    A recording replacement captures the arguments each statement form passes,
    which is the page's claim about what each form compiles to; `dis` confirms
    the instruction count independently.
    """

    @pytest.fixture
    def recording(self) -> Iterator[Recording]:
        installed = Recording()
        yield installed
        installed.stop()

    @staticmethod
    def _warm(*names: str) -> None:
        """Load these before recording, so only the statements under test count."""
        for name in names:
            importlib.import_module(name)

    @staticmethod
    def _import_names(source: str) -> int:
        return [
            instruction.opname
            for instruction in dis.get_instructions(compile(source, "<s>", "exec"))
        ].count("IMPORT_NAME")

    def test_each_named_module_compiles_to_one_import_name(self) -> None:
        for source in (
            "import xml.sax",
            "import xml.sax as s",
            "from xml import sax",
            "from xml.sax import handler, xmlreader",  # one module, two names
        ):
            assert self._import_names(source) == 1, source

        assert self._import_names("import xml, json") == 2  # two modules, one statement

    def test_each_form_passes_what_the_page_says(self, recording: Recording) -> None:
        self._warm("xml.sax", "xml.sax.handler", "xml.sax.xmlreader", "json.scanner")
        recording.start()
        namespace: dict[str, Any] = {"__name__": "json.decoder"}
        exec("import xml.sax", namespace)
        exec("import xml.sax as renamed", namespace)
        exec("from xml.sax import handler, xmlreader", namespace)
        exec("from . import scanner", namespace)
        exec("from xml import *", namespace)
        observed = recording.stop()

        assert observed == [
            ("xml.sax", None, 0),
            ("xml.sax", None, 0),
            ("xml.sax", ("handler", "xmlreader"), 0),
            ("", ("scanner",), 1),  # a bare `from . import x` names nothing
            ("xml", ("*",), 0),
        ]
        assert namespace["xml"].__name__ == "xml"  # `import xml.sax` binds the top package
        assert namespace["renamed"].__name__ == "xml.sax"
        assert namespace["handler"] is sys.modules["xml.sax.handler"]
        assert namespace["scanner"] is sys.modules["json.scanner"]

    def test_the_replacement_is_called_once_per_statement(self, recording: Recording) -> None:
        self._warm("json")
        recording.start()
        namespace: dict[str, Any] = {}
        exec("import json\nimport json\nimport json", namespace)
        observed = recording.stop()

        assert [name for name, _, _ in observed] == ["json", "json", "json"]

    def test_importlib_dunder_import_is_a_different_object(self, recording: Recording) -> None:
        self._warm("json")
        assert importlib.__import__ is not recording.original
        recording.start()

        importlib.__import__("json")
        observed = recording.stop()

        assert observed == []

    def test_a_module_loaded_that_way_still_imports_through_the_builtins_entry(
        self, recording: Recording, tmp_path: pathlib.Path
    ) -> None:
        """The call bypasses the entry; statements in the body it runs do not."""
        write_module(tmp_path, "nested_body", "import json\n")
        sys.path.insert(0, str(tmp_path))
        self._warm("json")
        recording.start()

        importlib.__import__("nested_body")
        observed = recording.stop()

        # The loader reaches the entry for its own imports too, so this is a
        # membership check: what matters is that the body's statement is there.
        assert "json" in [name for name, _, _ in observed]

    def test_a_frame_with_its_own_builtins_never_sees_the_replacement(
        self, recording: Recording
    ) -> None:
        self._warm("json")
        recording.start()
        isolated: dict[str, Any] = {
            "__name__": "isolated",
            "__builtins__": {"__import__": lambda *args, **kwargs: "not the real json"},
        }

        exec("taken = __import__('json')", isolated)
        exec("import json", isolated)
        observed = recording.stop()

        assert isolated["taken"] == "not the real json"
        assert isolated["json"] == "not the real json"
        assert observed == []

    def test_deleting_the_name_leaves_import_with_nothing_to_call(self) -> None:
        del builtins.__import__
        try:
            with pytest.raises(ImportError, match="__import__ not found"):
                exec("import json", {})
        finally:
            builtins.__import__ = importlib.__import__


class TestImportFromFallsBackToSysModules:
    """`import pkg.mod as name` and `from pkg.mod import x` | one attribute
    load, "with the same `sys.modules` fallback".

    Deleting the submodule attribute from a loaded package reaches the fallback
    deterministically, without building a circular import to provoke it.
    """

    def test_a_missing_attribute_is_taken_from_sys_modules(self, tmp_path: pathlib.Path) -> None:
        counting_package(tmp_path, "bpkg", ("leaf",))
        package = __import__("bpkg", fromlist=["leaf"])

        del package.leaf  # the package no longer carries the submodule
        package.CHECKS.clear()
        recorder = Recorder()
        sys.meta_path.insert(0, recorder)

        namespace: dict[str, Any] = {}
        exec("import bpkg.leaf as renamed", namespace)
        exec("from bpkg import leaf", namespace)

        assert namespace["renamed"] is sys.modules["bpkg.leaf"]
        assert namespace["leaf"] is sys.modules["bpkg.leaf"]
        # The fromlist check missed while `bpkg.leaf` was loaded, so the import
        # it triggered was a probe: no finder was reached.
        assert recorder.asked == []
        # The `as` form's attribute load, the second statement's `fromlist`
        # check, and its own attribute load: each missed, and each fell back.
        assert package.CHECKS == ["leaf", "leaf", "leaf"]


class TestStarBindsEveryExportedName:
    """`from pkg import *` | O(a): every name in `__all__` - or every name not
    starting with `_` - is bound in the importing namespace.

    Two modules separate the cases, and a second execution shows the binding is
    not cached.
    """

    def test_all_decides_what_is_bound(self, tmp_path: pathlib.Path) -> None:
        write_module(tmp_path, "listed", "__all__ = ['kept']\nkept = 1\ndropped = 2\n")
        write_module(tmp_path, "unlisted", "kept = 1\n_private = 2\n")
        sys.path.insert(0, str(tmp_path))

        listed: dict[str, Any] = {}
        exec("from listed import *", listed)
        assert listed["kept"] == 1
        assert "dropped" not in listed

        unlisted: dict[str, Any] = {}
        exec("from unlisted import *", unlisted)
        assert unlisted["kept"] == 1
        assert "_private" not in unlisted

    def test_each_execution_binds_again(self, tmp_path: pathlib.Path) -> None:
        write_module(tmp_path, "listed", "__all__ = ['kept']\nkept = 1\n")
        sys.path.insert(0, str(tmp_path))

        namespace: dict[str, Any] = {}
        exec("from listed import *", namespace)
        namespace["kept"] = "overwritten"
        exec("from listed import *", namespace)

        assert namespace["kept"] == 1


class TestAFunctionLevelImportRunsOnce:
    """A function-level import runs the module body on the first call that
    reaches it.

    A sentinel list separates "not until the call" from "not at all" and
    "once" from "once per call".
    """

    def test_the_body_waits_for_the_call_and_runs_once(self, tmp_path: pathlib.Path) -> None:
        runs = sentinel("deferred_sentinel")
        write_module(
            tmp_path,
            "heavy",
            "import deferred_sentinel\ndeferred_sentinel.RUNS.append('heavy')\n",
        )
        sys.path.insert(0, str(tmp_path))

        namespace: dict[str, Any] = {}
        exec("def use():\n    import heavy\n    return heavy\n", namespace)
        assert runs.RUNS == []  # type: ignore[attr-defined]

        first = namespace["use"]()
        assert runs.RUNS == ["heavy"]  # type: ignore[attr-defined]
        assert namespace["use"]() is first
        assert runs.RUNS == ["heavy"]  # type: ignore[attr-defined]


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
    """Each block runs in its own subprocess, so a replaced `builtins.__import__`,
    a blocked `sys.modules` entry and the modules a block imports cannot leak
    between them."""

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
        line, source = next((n, s) for n, s in _blocks() if 'top.__name__ == "json"' in s)
        mutated = source.replace('top.__name__ == "json"', 'top.__name__ == "json.decoder"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
