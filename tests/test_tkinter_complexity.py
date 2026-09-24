"""Tests for docs/stdlib/tkinter.md.

Lib/tkinter/__init__.py: every widget method is one ``tk.call`` on the
interpreter the root created with ``_tkinter.create``. ``Tk.__init__``
runs ``readprofile``, which sources ``~/.<className>.tcl`` and
``~/.<baseName>.tcl`` and ``exec``s the two matching ``.py`` files unless
``sys.flags.ignore_environment`` is set; ``Tcl()`` is ``Tk(useTk=False)``,
and ``_tkinter``'s ``mainloop`` loops only while ``Tk_GetNumMainWindows()``
is above zero, so without Tk it returns before dispatching anything.
``Misc._options`` merges the option dicts, replaces each callable value by
``_register``, which creates one Tcl command named from ``id()`` and the
function name and appends that name to the widget's ``_tclCommands`` list,
and builds the argument tuple by ``res = res + ('-' + k, v)`` once per
option. ``ttk._format_optdict`` appends to a list and flattens it once.
``deletecommand`` deletes the Tcl command and ``list.remove``s the name;
``Misc.destroy`` deletes every name in the list; ``BaseWidget.destroy``
recurses through ``children`` first. ``after`` registers a wrapper that
deletes its own command in a ``finally``; ``after_cancel`` reads ``after
info`` to find that command, deletes it and cancels the timer;
``after_idle`` is ``after('idle', ...)``. ``BaseWidget._setup`` names a
widget from a per-master ``_last_child_ids`` counter and destroys any
existing child of the same name. ``Variable.__init__`` names the Tcl
variable ``PY_VAR<n>`` from a module counter and initializes it only when
a value is given or the name does not yet exist; ``trace_add`` registers a
command and one trace; ``trace_remove`` lists the remaining traces and
deletes the command only when none names it; ``__del__`` unsets the
variable and deletes the commands. ``CallWrapper.__call__`` runs ``subst``
then ``func`` and hands any exception but SystemExit to
``Tk.report_callback_exception``, which prints to stderr and sets the
``sys.last_*`` attributes.

Observation settles every row the interpreter alone can reach:

* ``Tcl()`` runs the four profile files from ``HOME`` and skips them under
  ``-E``; ``mainloop()`` returns with its one-second timer still pending,
  well inside that second; ``Tk.master`` is None, ``Tk.children`` empty, and attributes
  ``Tk`` lacks come from the interpreter object; a bad command raises
  TclError; ``getint`` and ``getdouble`` are ``int`` and ``float``, and the
  module ``getboolean()``, ``mainloop()`` and ``image_names()`` raise
  RuntimeError with no root, as every constructor does after
  ``NoDefaultRoot()``;
* ``register()`` creates one command whose name carries the function's
  name and appends it to the registry; ``deletecommand()`` removes both;
  ``Misc.destroy()`` deletes all of them; with a Tcl proc standing in for
  the ``frame`` command, widgets are named ``!frame``, ``!frame2`` and
  ``.!frame.!frame``, ``nametowidget()`` walks the path, a repeated
  ``name=`` destroys the earlier widget, ``configure(command=f)``
  registers one command that ``destroy()`` deletes, and destroying a
  widget with d descendants issues d + 1 ``destroy`` commands;
* ``after()`` registers one command per call and returns an id;
  ``update()`` runs a due timer and an idle callback, timer first, and the
  command is gone afterwards; ``after_cancel()`` removes the timer and the
  command and raises ValueError on ``''``; ``after(ms)`` blocks for at
  least ms; ``after_info(id)`` reports ``timer`` or ``idle`` on 3.13+; a
  callback that raises prints ``Exception in Tkinter callback`` and sets
  ``sys.last_value`` instead of propagating;
* variables are ``PY_VAR<n>`` with n increasing; a second object over an
  existing name keeps its value; ``IntVar.get()`` truncates ``"2.5"``,
  ``BooleanVar.set("yes")`` stores True and ``get()`` of ``"maybe"``
  raises ValueError; ``trace_add`` runs the callback with the variable
  name, the empty index and the mode, ``trace_info`` lists every trace, and
  ``trace_remove`` with a different mode list removes nothing and with the
  original one removes the trace and its command; ``del`` unsets the
  variable and deletes the command; the three ``trace_v*`` methods warn on
  3.14+ and not before, and raise TclError under Tcl 9 and succeed under 8;
* ``EventType`` is a ``str`` enum, ``ttk.setup_master(x)`` is ``x``,
  ``ttk.tclobjs_to_py`` converts in place, and the interpreter returns a
  typed int under ``wantobjects``.

The stopwatch tests, on one interpreter each: ``_options``, which every
widget constructor and ``configure()`` uses, ttk's included, on 1000 and
4000 options, where the tuple rebuild makes the ratio near 16 and a
linear formatter would give 4, against ``ttk._format_optdict``, which the
``Style`` and item methods use, on the same sizes, which stays near 4; ``deletecommand()`` of the last 200 of 20000
and of 80000 registered commands, near 4 for the list scan; ``register()``
of 2000 commands on an empty registry and on one holding 80000, near 1
with the garbage collector paused, since the full registry's 80000 closures
would otherwise be traversed by a collection the measurement triggers; and
``trace_info()`` and removal of the newest trace on 200, 2000 and 20000
traces. Each 10x step must cost more than 20x (linear predicts 10x,
quadratic 100x). Both use the fastest of five samples with cyclic GC
paused; removal restores the trace outside the timer before the next sample.
Tcl's ``trace info variable`` restarts its walk of the trace list for
every trace it reports. Trace modes and callback bodies are held fixed.

Not settled by running code, because every Tk window needs a display and
neither the pinned interpreter here nor CI has one: the widget, window
manager, geometry manager, canvas, text, listbox, menu, image, font,
dialog and ttk rows. Their bounds come from Tk 9.0's C sources: the
canvas keeps items in a doubly linked display list with an id hash table
(``tkCanvas.c``, ``TagSearchFirst``), the listbox in one Tcl list object
with the selection and item attributes in hash tables keyed by index
(``tkListbox.c``, ``ListboxInsertSubCmd``), the menu in an entry array
copied on every add (``tkMenu.c``, ``MenuNewEntry``), the text widget in a
B-tree of lines (``tkTextBTree.c``, ``TkBTreeFindLine``), the treeview in
a hash table of items whose children are a linked list walked by index,
with the last child cached for ``END`` (``ttkTreeview.c``, ``EndPosition``), the grid's size and bounding box from a scan of its
content (``tkGrid.c``, ``SetGridSize``), the paned window in an array
rebuilt on add (``tkPanedWindow.c``), ``tk_focusNext`` from ``winfo
children`` at each level (``library/focus.tcl``) and ``flash`` from four
50 ms sleeps (``tkButton.c``). ``Menu.delete`` and ``Text.dump`` are
Python code read but not run. Not varied: the option values' types beyond
strings and one callable, more than one interpreter, and the Tcl side of
``trace remove``, which is linear in the traces as well.
"""

import gc
import inspect
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import timeit
import types
import warnings
from collections.abc import Callable
from typing import Any, cast

import pytest

tkinter = pytest.importorskip("tkinter")
ttk = pytest.importorskip("tkinter.ttk")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tkinter.md"
EXPECTED_BLOCKS = 3

SUBMODULES: dict[str, types.ModuleType] = {
    name: pytest.importorskip(f"tkinter.{name}")
    for name in (
        "ttk",
        "font",
        "filedialog",
        "messagebox",
        "simpledialog",
        "commondialog",
        "dialog",
        "colorchooser",
        "scrolledtext",
        "dnd",
    )
}
MODULES: dict[str, types.ModuleType] = {"tkinter": tkinter, **SUBMODULES}

# Demonstration code the modules ship but the official documentation does not
# describe: the drag-and-drop demo classes and the ``test``/``example``
# functions that open windows, plus filedialog's per-key memory dict.
UNDOCUMENTED_NAMES: dict[str, set[str]] = {
    "dnd": {"Icon", "Tester", "test"},
    "filedialog": {"test", "dialogstates"},
    "scrolledtext": {"example"},
}

# Attributes an instance carries that the class does not, all documented as
# rows of their own.
INSTANCE_ATTRIBUTES: set[tuple[str, str, str]] = {
    ("tkinter", "Tk", "tk"),
    ("tkinter", "Tk", "master"),
    ("tkinter", "Tk", "children"),
    ("simpledialog", "Dialog", "result"),
    ("scrolledtext", "ScrolledText", "frame"),
    ("scrolledtext", "ScrolledText", "vbar"),
} | {
    ("tkinter", "Event", field)
    for field in (
        "serial num focus height width keycode state time x y x_root y_root "
        "char send_event keysym keysym_num type widget delta"
    ).split()
}

VERSION_GATED: dict[tuple[str, str, str], tuple[tuple[int, int], str]] = {
    ("tkinter", "Misc", "after_info"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "tk_busy_hold"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "tk_busy_forget"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "tk_busy_configure"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "tk_busy_cget"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "tk_busy_current"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "tk_busy_status"): ((3, 13), "Python 3.13+"),
    ("tkinter", "Misc", "info_patchlevel"): ((3, 11), "Python 3.11+"),
    ("tkinter", "PhotoImage", "copy_replace"): ((3, 13), "Python 3.13+"),
    ("tkinter", "PhotoImage", "read"): ((3, 13), "Python 3.13+"),
    ("tkinter", "PhotoImage", "data"): ((3, 13), "Python 3.13+"),
}

PY = sys.executable
FAKE_WIDGET_PROCS = """
    proc frame {name args} { proc $name {args} {} }
    proc destroy {args} { incr ::destroyed }
"""


def _table_rows() -> list[str]:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("## Callbacks Are Not Free", start)
    return [line for line in text[start:end].splitlines() if line.startswith("| `")]


def _parse(span: str) -> tuple[str, str, str | None]:
    """``ttk.Treeview.insert(parent, index)`` -> ("ttk", "Treeview", "insert").

    A span without a submodule prefix belongs to ``tkinter``; one without a
    dot is a module-level name and comes back with member None.
    """
    name = span.split("(", 1)[0].strip()
    parts = name.split(".")
    module = "tkinter"
    if parts[0] in SUBMODULES:
        module = parts.pop(0)
    if len(parts) == 1:
        return module, parts[0], None
    assert len(parts) == 2, f"cannot parse table span {span!r}"
    return module, parts[0], parts[1]


def _documented() -> tuple[set[tuple[str, str]], set[tuple[str, str, str]]]:
    """(module, name) pairs and (module, class, member) triples the table names.

    ``del`` is a row about garbage collection, not a name.
    """
    names: set[tuple[str, str]] = set()
    members: set[tuple[str, str, str]] = set()
    for row in _table_rows():
        operation = row.split("|")[1]
        for span in re.findall(r"`([^`]+)`", operation):
            if span == "del":
                continue
            module, owner, member = _parse(span)
            names.add((module, owner))
            if member is not None:
                members.add((module, owner, member))
    return names, members


def _module_names(module_name: str) -> set[str]:
    """Public non-constant names the module defines or, for tkinter, exports."""
    module = MODULES[module_name]
    names: set[str] = set()
    for name, value in vars(module).items():
        if name.startswith("_") or isinstance(value, types.ModuleType) or name.isupper():
            continue
        if module_name != "tkinter" and getattr(tkinter, name, None) is value:
            continue  # a ``from tkinter import *`` re-export
        defined_in = getattr(value, "__module__", None)
        if isinstance(defined_in, str) and defined_in.startswith("tkinter"):
            if defined_in != module.__name__:
                continue  # a re-export such as colorchooser's commondialog.Dialog
        names.add(name)
    return names - UNDOCUMENTED_NAMES.get(module_name, set())


def _classes() -> dict[tuple[str, str], type]:
    found: dict[tuple[str, str], type] = {}
    for module_name in MODULES:
        for name in _module_names(module_name):
            value = getattr(MODULES[module_name], name)
            if isinstance(value, type) and value.__module__ == MODULES[module_name].__name__:
                found[(module_name, name)] = value
    return found


def _own_members(cls: type) -> dict[str, object]:
    """Public callables and properties the class itself defines."""
    return {
        name: value
        for name, value in vars(cls).items()
        if not name.startswith("_") and (callable(value) or isinstance(value, property))
    }


def _has_member(module_name: str, owner: str, member: str) -> bool:
    if (module_name, owner, member) in INSTANCE_ATTRIBUTES:
        return True
    cls = getattr(MODULES[module_name], owner, None)
    if cls is None:
        return False
    gate = VERSION_GATED.get((module_name, owner, member))
    if gate is not None and sys.version_info < gate[0]:
        return True
    return hasattr(cls, member)


def _tcl() -> Any:
    return tkinter.Tcl()


def _pending_timers(root: Any) -> tuple[str, ...]:
    return tuple(root.tk.splitlist(root.tk.call("after", "info")))


def _command_exists(root: Any, name: str) -> bool:
    return bool(root.tk.splitlist(root.tk.call("info", "commands", name)))


def _registry(widget: Any) -> list[str]:
    return list(cast(Any, widget)._tclCommands or [])


def _best(func: Callable[[], object], number: int = 1, repeat: int = 5) -> float:
    return min(timeit.repeat(func, number=number, repeat=repeat)) / number


class TestEveryPublicNameIsDocumented:
    """The table names every public name of tkinter and its ten submodules."""

    @pytest.mark.parametrize("module_name", sorted(MODULES))
    def test_no_module_name_is_missing_from_the_table(self, module_name: str) -> None:
        names = {name for module, name in _documented()[0] if module == module_name}
        missing = sorted(_module_names(module_name) - names)

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_no_public_member_is_missing_from_the_table(self) -> None:
        """A member that is the same object as a documented one is an alias."""
        members = _documented()[1]
        documented_objects = {
            getattr(getattr(MODULES[module], owner), member)
            for module, owner, member in members
            if hasattr(getattr(MODULES[module], owner, None), member)
        }
        missing: list[str] = []
        for (module_name, owner), cls in sorted(_classes().items()):
            for member, value in _own_members(cls).items():
                if (module_name, owner, member) in members:
                    continue
                if any(value is other for other in documented_objects):
                    continue
                missing.append(f"{module_name}.{owner}.{member}")

        assert not missing, f"{len(missing)} members absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        names, members = _documented()

        unknown_names = sorted(
            f"{module}.{name}" for module, name in names if not hasattr(MODULES[module], name)
        )
        unknown_members = sorted(
            f"{module}.{owner}.{member}"
            for module, owner, member in members
            if not _has_member(module, owner, member)
        )

        assert not unknown_names, f"the table names attributes that do not exist: {unknown_names}"
        assert not unknown_members, f"the table names members that do not exist: {unknown_members}"

    def test_the_version_gated_rows_say_so(self) -> None:
        rows = _table_rows()
        for (module, owner, member), (_, marker) in VERSION_GATED.items():
            spelled = (
                f"`{owner}.{member}(" if module == "tkinter" else f"`{module}.{owner}.{member}("
            )
            owning = [row for row in rows if spelled in row]
            assert len(owning) == 1, f"expected one row naming {spelled}, found {len(owning)}"
            assert marker in owning[0], f"the {member} row should say {marker}: {owning[0]}"

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        names, members = _documented()

        assert {
            ("tkinter", "Tcl"),
            ("tkinter", "Misc"),
            ("ttk", "Treeview"),
            ("font", "Font"),
        } <= names
        assert {
            ("tkinter", "Misc", "after_cancel"),
            ("tkinter", "Variable", "trace_remove"),
            ("tkinter", "Text", "search"),
            ("ttk", "Treeview", "insert"),
            ("filedialog", "FileDialog", "filter_command"),
        } <= members
        assert ("tkinter", "Misc", "after") in members
        assert "after" in _own_members(tkinter.Misc)
        without = members - {("tkinter", "Misc", "after")}
        assert not any(
            tkinter.Misc.after is getattr(getattr(MODULES[m], o), n)
            for m, o, n in without
            if hasattr(getattr(MODULES[m], o, None), n)
        ), "after has no alias, so dropping its row would have to fail the member check"


class TestTclInterpreter:
    """Rows of the Tk and Tcl section that need no window."""

    def test_tcl_is_an_interpreter_without_tk(self) -> None:
        root = _tcl()

        assert root.master is None
        assert root.children == {}
        assert root.tk.call("expr", "1+1") == 2, "wantobjects returns typed results"
        assert root.splitlist("a b") == ("a", "b"), "unknown attributes come from Tk.tk"
        with pytest.raises(tkinter.TclError):
            root.tk.call("winfo", "id", ".")
        with pytest.raises(tkinter.TclError):
            root.bind("<Key>", lambda event: None)

    def test_mainloop_returns_at_once_without_a_tk_window(self) -> None:
        root = _tcl()
        root.after(1000, lambda: None)

        start = time.perf_counter()
        root.mainloop()
        elapsed = time.perf_counter() - start

        assert elapsed < 0.9, f"mainloop blocked for {elapsed:.3f}s"
        assert len(_pending_timers(root)) == 1, "the timer never got to fire"

    def test_getint_and_getdouble_are_int_and_float(self) -> None:
        assert tkinter.getint is int
        assert tkinter.getdouble is float
        root = _tcl()
        assert root.getint("7") == 7
        assert root.getdouble("1.5") == 1.5
        assert root.getboolean("yes") is True
        root.setvar("answer", "42")
        assert root.getvar("answer") == "42"
        assert isinstance(tkinter.TkVersion, float)
        assert tkinter.wantobjects == 1

    def test_the_module_functions_need_a_default_root(self) -> None:
        for call in (tkinter.getboolean, tkinter.mainloop, tkinter.image_names):
            with pytest.raises(RuntimeError, match="Too early"):
                call("1") if call is tkinter.getboolean else call()

    def test_no_default_root_makes_masterless_widgets_variables_and_images_raise(self) -> None:
        """A separate process: NoDefaultRoot() cannot be undone."""
        code = textwrap.dedent(
            """
            import tkinter
            tkinter.NoDefaultRoot()
            for factory in (tkinter.StringVar, tkinter.Frame, tkinter.PhotoImage):
                try:
                    factory()
                except RuntimeError as error:
                    print(type(error).__name__, "default root" in str(error))
            """
        )
        result = subprocess.run([PY, "-c", code], capture_output=True, text=True, check=True)

        assert result.stdout.splitlines() == ["RuntimeError True"] * 3

    def test_tk_runs_the_profile_files_from_home_unless_ignoring_the_environment(
        self, tmp_path: pathlib.Path
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        (home / ".Tk.tcl").write_text("set ::from_class_tcl 1\n", encoding="utf-8")
        (home / ".Tk.py").write_text("self.setvar('from_class_py', 1)\n", encoding="utf-8")
        (home / ".prof.tcl").write_text("set ::from_base_tcl 1\n", encoding="utf-8")
        (home / ".prof.py").write_text("self.setvar('from_base_py', 1)\n", encoding="utf-8")
        script = tmp_path / "prof.py"
        script.write_text(
            textwrap.dedent(
                """
                import tkinter
                root = tkinter.Tcl()
                names = ("from_class_tcl", "from_class_py", "from_base_tcl", "from_base_py")
                print(*(root.tk.call("info", "exists", name) for name in names))
                """
            ),
            encoding="utf-8",
        )
        env = {**os.environ, "HOME": str(home)}

        plain = subprocess.run(
            [PY, str(script)], capture_output=True, text=True, env=env, check=True
        )
        ignoring = subprocess.run(
            [PY, "-E", str(script)], capture_output=True, text=True, env=env, check=True
        )

        assert plain.stdout.split() == ["1", "1", "1", "1"]
        assert ignoring.stdout.split() == ["0", "0", "0", "0"]


class TestCommandRegistry:
    """register(), deletecommand(), destroy() and the widget tree."""

    def test_register_creates_one_named_command_in_the_registry(self) -> None:
        root = _tcl()

        def answer() -> int:
            return 42

        name = root.register(answer)

        assert name.endswith("answer")
        assert _command_exists(root, name)
        assert root.tk.call(name) == 42
        assert _registry(root) == [name]

        root.deletecommand(name)

        assert not _command_exists(root, name)
        assert _registry(root) == []

    def test_misc_destroy_deletes_every_registered_command(self) -> None:
        root = _tcl()
        names = [root.register(lambda: None) for _ in range(5)]

        tkinter.Misc.destroy(root)

        assert not any(_command_exists(root, name) for name in names)
        assert cast(Any, root)._tclCommands is None

    def test_widgets_are_named_from_a_per_master_counter(self) -> None:
        root = _tcl()
        root.tk.eval(FAKE_WIDGET_PROCS)

        first = tkinter.Frame(root)
        second = tkinter.Frame(root)
        inner = tkinter.Frame(first)

        assert str(first) == ".!frame"
        assert str(second) == ".!frame2"
        assert str(inner) == ".!frame.!frame"
        assert root.children == {"!frame": first, "!frame2": second}
        assert root.nametowidget(".!frame.!frame") is inner
        assert first.nametowidget("!frame") is inner
        assert inner._root() is root

    def test_a_repeated_name_destroys_the_earlier_widget(self) -> None:
        root = _tcl()
        root.tk.eval(FAKE_WIDGET_PROCS)
        root.tk.setvar("destroyed", 0)

        old = tkinter.Frame(root, name="same")
        new = tkinter.Frame(root, name="same")

        assert root.getvar("destroyed") == 1
        assert root.children == {"same": new}
        assert old is not new

    def test_a_callable_option_registers_a_command_that_destroy_deletes(self) -> None:
        root = _tcl()
        root.tk.eval(FAKE_WIDGET_PROCS)
        frame = tkinter.Frame(root)

        frame.configure(command=lambda: None)
        (name,) = _registry(frame)

        assert _command_exists(root, name)
        frame.destroy()
        assert not _command_exists(root, name)
        assert "!frame" not in root.children

    def test_destroy_recurses_through_every_descendant(self) -> None:
        root = _tcl()
        root.tk.eval(FAKE_WIDGET_PROCS)
        root.tk.setvar("destroyed", 0)
        outer = tkinter.Frame(root)
        middle = tkinter.Frame(outer)
        leaves = [tkinter.Frame(middle) for _ in range(3)]

        outer.destroy()

        assert root.getvar("destroyed") == 1 + 1 + len(leaves)
        assert root.children == {}
        assert outer.children == {}

    def test_option_marshalling_beyond_one_option(self) -> None:
        root = _tcl()
        root.tk.eval("proc keep {args} { set ::seen $args }")
        root.tk.setvar("seen", "")
        frame_like = cast(Any, root)

        args = frame_like._options({"width": 3, "class_": "X", "skip": None})
        root.tk.call("keep", *args)

        assert root.tk.splitlist(root.getvar("seen")) == ("-width", 3, "-class", "X")


class TestAfter:
    """The after family under update(), which is what a mainloop would do."""

    def test_after_registers_one_command_and_update_runs_what_is_due(self) -> None:
        root = _tcl()
        fired: list[str] = []

        ident = root.after(0, fired.append, "timer")
        root.after_idle(fired.append, "idle")

        assert isinstance(ident, str) and ident.startswith("after#")
        assert len(_registry(root)) == 2
        assert len(_pending_timers(root)) == 2

        root.update()

        assert fired == ["timer", "idle"]
        assert _registry(root) == [], "each callback deleted its own command"
        assert _pending_timers(root) == ()

    def test_after_cancel_removes_the_timer_and_the_command(self) -> None:
        root = _tcl()
        fired: list[str] = []
        ident = root.after(0, fired.append, "cancelled")
        (name,) = _registry(root)

        root.after_cancel(ident)

        assert _pending_timers(root) == ()
        assert not _command_exists(root, name)
        assert _registry(root) == []
        root.update()
        assert fired == []
        with pytest.raises(ValueError):
            root.after_cancel("")

    def test_after_without_a_function_blocks(self) -> None:
        root = _tcl()

        start = time.perf_counter()
        returned = root.after(50)
        elapsed = time.perf_counter() - start

        assert returned is None
        assert elapsed >= 0.045, f"after(50) returned after {elapsed * 1000:.1f} ms"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="after_info() is Python 3.13+")
    def test_after_info_reports_one_timer_or_all_of_them(self) -> None:
        root = _tcl()
        timer = root.after(1000, lambda: None)
        idle = root.after_idle(lambda: None)

        assert root.after_info(timer)[1] == "timer"
        assert root.after_info(idle)[1] == "idle"
        assert set(root.after_info()) == {timer, idle}

    def test_a_callback_exception_is_reported_not_raised(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _tcl()
        error = ValueError("from the callback")

        def explode() -> None:
            raise error

        root.after(0, explode)
        root.update()

        assert "Exception in Tkinter callback" in capsys.readouterr().err
        assert sys.last_value is error

    def test_callwrapper_substitutes_then_calls_and_lets_systemexit_through(self) -> None:
        root = _tcl()
        wrapper = tkinter.CallWrapper(lambda *args: args, lambda *args: ("subst", *args), root)

        assert wrapper("a", "b") == ("subst", "a", "b")

        def leave() -> None:
            raise SystemExit(3)

        with pytest.raises(SystemExit):
            tkinter.CallWrapper(leave, None, root)()


class TestVariables:
    """Variable, its subclasses and their traces."""

    def test_names_come_from_a_counter_and_an_existing_name_keeps_its_value(self) -> None:
        root = _tcl()

        first = tkinter.StringVar(master=root, value="a")
        second = tkinter.StringVar(master=root)

        assert re.fullmatch(r"PY_VAR\d+", str(first))
        assert int(str(second)[6:]) == int(str(first)[6:]) + 1
        assert second.get() == ""
        assert first.get() == "a"

        same = tkinter.StringVar(master=root, name=str(first))
        assert same.get() == "a"
        assert same == first
        replaced = tkinter.StringVar(master=root, name=str(first), value="b")
        assert first.get() == "b"
        assert replaced.get() == "b"

    def test_get_converts_to_the_subclass_type(self) -> None:
        root = _tcl()
        integer = tkinter.IntVar(master=root)
        boolean = tkinter.BooleanVar(master=root)
        double = tkinter.DoubleVar(master=root, value=2)

        root.setvar(str(integer), "2.5")
        assert integer.get() == 2
        boolean.set("yes")
        assert boolean.get() is True
        root.setvar(str(boolean), "maybe")
        with pytest.raises(ValueError):
            boolean.get()
        assert double.get() == 2.0 and isinstance(double.get(), float)
        assert tkinter.Variable(master=root).get() == ""

    def test_trace_add_runs_the_callback_inside_set(self) -> None:
        root = _tcl()
        var = tkinter.IntVar(master=root, value=1)
        calls: list[tuple[Any, ...]] = []

        name = var.trace_add("write", lambda *args: calls.append((*args, var.get())))
        var.set(5)

        assert calls == [(str(var), "", "write", 5)]
        assert var.trace_info() == [(("write",), name)]
        assert _command_exists(root, name)

    def test_trace_remove_needs_the_mode_list_the_trace_was_added_with(self) -> None:
        root = _tcl()
        var = tkinter.StringVar(master=root)
        name = var.trace_add(("read", "write"), lambda *args: None)

        var.trace_remove("write", name)

        assert var.trace_info() == [(("read", "write"), name)]
        assert _command_exists(root, name)

        var.trace_remove(("read", "write"), name)

        assert var.trace_info() == []
        assert not _command_exists(root, name)

    def test_deleting_the_variable_unsets_it_and_its_commands(self) -> None:
        root = _tcl()
        var = tkinter.StringVar(master=root, value="x")
        tcl_name = str(var)
        command = var.trace_add("write", lambda *args: None)

        del var

        assert root.tk.call("info", "exists", tcl_name) == 0
        assert not _command_exists(root, command)

    def test_the_legacy_trace_methods_warn_from_3_14_and_fail_under_tcl_9(self) -> None:
        root = _tcl()
        var = tkinter.StringVar(master=root)
        outcomes: list[str] = []

        for call in (
            lambda: var.trace_variable("w", lambda *args: None),
            lambda: var.trace_vinfo(),
            lambda: var.trace_vdelete("w", "nosuchcommand"),
        ):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    call()
                except tkinter.TclError:
                    outcomes.append("TclError")
                else:
                    outcomes.append("ok")
            warned = any(issubclass(w.category, DeprecationWarning) for w in caught)
            assert warned == (sys.version_info >= (3, 14))

        expected = "TclError" if tkinter.TclVersion >= 9 else "ok"
        assert outcomes == [expected] * 3


class TestSmallRows:
    def test_eventtype_is_a_str_enum(self) -> None:
        key_press = cast(Any, tkinter.EventType.KeyPress)
        assert str in tkinter.EventType.__mro__
        assert key_press.name == "KeyPress"
        assert key_press == "2"
        assert tkinter.EventType("2") is key_press
        event = cast(Any, tkinter.Event())
        event.type = key_press
        event.widget = None
        assert event.type is key_press

    def test_ttk_helpers(self) -> None:
        root = _tcl()

        assert ttk.setup_master(root) is root
        values = {"a": root.tk.call("list", 1, 2), "b": "text", "c": ()}
        converted = ttk.tclobjs_to_py(values)
        assert converted is values
        assert converted == {"a": [1, 2], "b": "text", "c": ""}


@pytest.mark.timing
class TestGrowth:
    def test_option_marshalling_is_quadratic_and_ttk_formatting_linear(self) -> None:
        root = cast(Any, _tcl())
        small = {f"option{i}": "v" for i in range(1000)}
        large = {f"option{i}": "v" for i in range(4000)}

        classic = _best(lambda: root._options(large)) / _best(lambda: root._options(small), 3)
        themed = _best(lambda: ttk._format_optdict(large), 3) / _best(
            lambda: ttk._format_optdict(small), 10
        )

        assert classic > 8, f"4x the options cost x{classic:.1f} through _options"
        assert themed < 8, f"4x the options cost x{themed:.1f} through _format_optdict"
        assert "_format_optdict" not in inspect.getsource(tkinter.BaseWidget.__init__)
        assert "_options" in inspect.getsource(tkinter.BaseWidget.__init__)
        assert "tkinter.Widget.__init__" in inspect.getsource(ttk.Widget.__init__)

    def test_deletecommand_scans_the_registry_and_register_does_not(self) -> None:
        def registered(count: int) -> Any:
            root = _tcl()
            for _ in range(count):
                root.register(lambda: None)
            return root

        def delete_last(root: Any, how_many: int) -> Callable[[], None]:
            names = _registry(root)[-how_many:]

            def run() -> None:
                for name in reversed(names):
                    root.deletecommand(name)

            return run

        small, large = registered(20000), registered(80000)
        delete_ratio = _best(delete_last(large, 200), repeat=1) / _best(
            delete_last(small, 200), repeat=1
        )

        empty, full = _tcl(), registered(80000)

        def register(root: Any) -> Callable[[], None]:
            def run() -> None:
                for _ in range(2000):
                    root.register(lambda: None)

            return run

        gc.disable()
        try:
            register_ratio = _best(register(full), repeat=3) / _best(register(empty), repeat=3)
        finally:
            gc.enable()

        assert delete_ratio > 2.5, f"4x the commands made deletecommand x{delete_ratio:.1f}"
        assert register_ratio < 2, f"40x the commands made register x{register_ratio:.1f}"

    def test_trace_info_and_trace_remove_are_quadratic_in_the_traces(self) -> None:
        sizes = (200, 2000, 20000)
        timings: dict[str, list[float]] = {"trace_info": [], "trace_remove": []}
        for count in sizes:
            var = tkinter.StringVar(master=_tcl())
            for _ in range(count - 1):
                var.trace_add("write", lambda *args: None)
            name = var.trace_add("write", lambda *args: None)

            gc_enabled = gc.isenabled()
            gc.disable()
            try:
                timings["trace_info"].append(_best(var.trace_info))
                samples = []
                for _ in range(5):
                    start = time.perf_counter()
                    var.trace_remove("write", name)
                    samples.append(time.perf_counter() - start)
                    name = var.trace_add("write", lambda *args: None)
                timings["trace_remove"].append(min(samples))
            finally:
                if gc_enabled:
                    gc.enable()
            assert len(var.trace_info()) == count
            del var

        for operation, times in timings.items():
            for index in range(len(sizes) - 1):
                ratio = times[index + 1] / times[index]
                assert ratio > 20, (
                    f"{operation}: {sizes[index]} -> {sizes[index + 1]} traces "
                    f"cost x{ratio:.2f}; seconds at {sizes}: {times}"
                )


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


def _stated_outputs() -> list[str]:
    """The plain fenced blocks that follow each python block."""
    text = PAGE.read_text(encoding="utf-8")
    return [match.strip() for match in re.findall(r"Output:\n\n```\n(.*?)```", text, re.S)]


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [PY, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _needs_display(result: subprocess.CompletedProcess[str]) -> bool:
    """Tk() failed for want of a display, before any later line ran."""
    return "TclError" in result.stderr and "display" in result.stderr


class TestDocumentedExamples:
    """The Tcl() block runs everywhere; the two Tk() blocks need a display.

    Without one they fail on their first line, so here they are compiled, and
    run only far enough to prove that is the failure. Their stated outputs
    are checked wherever a display lets them run to the end.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        assert len(_stated_outputs()) == EXPECTED_BLOCKS

    def test_every_block_compiles_and_runs_or_needs_a_display(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for (line, source), stated in zip(_blocks(), _stated_outputs(), strict=True):
            compile(source, f"{PAGE.name}:{line}", "exec")
            result = _run(source, tmp_path)
            if result.returncode == 0 and not result.stderr.strip():
                if result.stdout.strip() != stated:
                    failures.append(f"{PAGE.name}:{line}: printed {result.stdout!r}")
            elif not ("tk.Tk()" in source and _needs_display(result)):
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_tcl_block_runs_without_a_display(self, tmp_path: pathlib.Path) -> None:
        (block,) = [source for _, source in _blocks() if "tk.Tcl()" in source]

        result = _run(block, tmp_path)

        assert result.returncode == 0, result.stderr.strip()
        assert result.stdout.strip() == _stated_outputs()[0]

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        (block,) = [source for _, source in _blocks() if "tk.Tcl()" in source]
        broken = block.replace("counter.set(10)", "countr.set(10)", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
