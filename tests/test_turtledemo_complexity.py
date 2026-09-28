"""Tests for docs/stdlib/turtledemo.md.

The page prices the demos in turtle commands - moves, turns, clones, stamps -
and the Python work around them, leaving what one command costs to
docs/stdlib/turtle.md. Every demo runs its real code on the recording canvas
from tests/test_turtle_complexity.py, extended to accept any colour name and
to keep the callbacks passed to `after()` and `bind()`, so no display is
needed. Commands are
counted by wrapping `RawTurtle._goto` (every move), `RawTurtle._rotate` (every
turn) and `RawTurtle.clone`; the sorting helpers are driven on stand-in blocks
that count their moves and size reads; `time.sleep` is replaced by a recorder.

Measurement scope:

* Importing `turtledemo` and all nineteen demos in a fresh interpreter whose
  `tkinter.Tk` raises creates no screen and no Tk root, and in another fresh
  interpreter the package alone defines no public name. `python -m turtledemo.yinyang`, run through `runpy`
  on the recording screen, draws and then calls `mainloop()` once.
* `getExampleEntries()` returns the nineteen demos from the real directory,
  keeps `a.py` and `d.py` and drops `_b.py` and `c.txt` from a directory
  patched in, in the listing's order, and lists the directory once per
  call. `loadfile()` on a module placed on the package path runs its top
  level on the first of two loads only and inserts its whole source, equal
  to the file's text, into the text pane; it calls the screen's `clear()`
  once after a demo has run and not on a clean viewer. `startDemo()` calls
  it once on a clean viewer and twice after a demo has run, returns only
  after `main()` has, and marks a demo that returns `"EVENTLOOP"`
  event-driven; `stopIt()` then clears the screen, and does not while a demo
  is running.
* STOP is delivered from inside a canvas `update()`, where Tk would process
  the click: under `tracer(1)` at speed 0, a `main()` of 20 moves is stopped
  after the move whose frame delivered it, raises `Terminator` at the next
  move, and the viewer reports `"stopped!"`. Under `tracer(0)` 50 moves make
  no canvas `update()` at all, so a click has nowhere to arrive; the first
  `update()` delivers it, the move after it still completes, and the second
  `update()` raises. STOP delivered on the 31st frame of `forest.main()`
  ends one tree: `main()` still returns its runtime, with more than the four
  starting turtles and fewer than the 1,713 of a full run.
* `hilbert()` makes 4^L − 1 moves and (4/3)(4^L − 1) turns for L = 1 to 5,
  with one more Python frame of recursion per level; `fractal()` makes 4^L
  moves for L = 0 to 4 and `fractalgon(5, ...)` at level 2 makes 5·16 moves
  plus 2.
* `tree.tree()` makes no command when the generator is built, yields nothing,
  and makes q(2^L − 1) moves and clones for q = 1 and 2 pens, leaving q·2^L
  turtles: L = 10 from length 200 and L = 7 from 50 with factor 0.6375.
  `forest.tree()` with b = 3 and b = 2 at levels 2 to 5 yields once per
  branch, Σ b^j for j below L, makes Σ b^j clones for j from 1 to L, draws
  Σ b^j (L − j) moves, makes at most one branch's L − j moves and at most b
  clones per `next()`, and leaves every turtle on the screen; its deepest
  move runs L − 1 Python frames deeper than its first, one generator per
  level.
* `hanoi()` pushes 2^d − 1 discs for d = 1 to 6, and a recursion one frame
  deeper per disc.
* A stand-in shelf of n blocks: `pop(key)` and `insert(key, b)` each move
  n − 1 − key blocks sideways plus the block itself; `pop(0)` on 200,000
  blocks peaks above 1.6 MB of traced allocation, more than 20x `pop()` of
  the last block. `isort()` on sorted input makes 4x the blocks cost more
  than 12x the moves, from 40 to 160 blocks; `ssort()` reads sizes n(n − 1)
  times (two per comparison) on sorted and reversed input and moves nothing
  on sorted input; `qsort()` on reversed input takes more than 6x the moves
  for 2x the blocks, from 80 to 160, and on three shuffles each of 50 and
  800 blocks (fixed seeds) takes between 300x and 1,000x the moves for 16x
  the blocks, where n² predicts 256x and n³ 4,096x. On sorted and on
  reversed input it reads sizes more than 12x as often for 4x the blocks.
  Every sort leaves the shelf sorted.
* `replace()` returns strings of 10, 38, 150, 598 and 2,390 characters for 0
  to 4 passes of the snake rules; its traced peak grows more than 10x from 6
  passes to 8, and a timing test finds the 16x longer result costs less than
  40x the time, where quadratic appending would cost about 256x.
* Penrose inflation from `sun(300, L)` and `star(300, L)` is counted through
  a dictionary that counts its writes: one write per recursion leaf, five at
  L = 0. From L = 7 to 8 the writes grow by between 3.40 and 3.43 per level
  and the distinct tiles by between 2.5 and 3.0, and at L = 8 the writes
  exceed five times the tiles. `draw()` creates one canvas item per tile.
* `mn_eck(p, t, 19)` makes t² moves and t − 1 clones and leaves t turtles, for
  t = 4, 8 and 16.
* One `GravSys` step calls `pos()` more than 3.5x as often for 2x the bodies,
  from 6 to 12; `start()` with its step count cut to 420 and 4,200 leaves
  more than 8x the trail coordinates on the canvas.
* Every demo's `main()` runs to its documented return value on the recording
  screen: the sleeps recorded are `[3]` for `fractalcurves` and
  `lindenmayer` and `[1]` for `rosette`, and with `penrose.clock` frozen,
  sixteen 2-second pads plus the 2-second pause, 34 seconds in all, and
  seventeen printed tile counts. `chaos` calls `setworldcoordinates()` 101
  times; `clock` leaves one 100 ms timer whose callback leaves another; a
  `colormixer` drag sets the background from the three sliders; `forest`
  leaves 1,713 turtles; `bytedesign` updates the screen at least 25 times
  under `tracer(0)`; the handler `minimal_hanoi` binds to the space bar
  moves all six discs to the last peg; `nim` builds 93 sticks, and a computer reply that takes
  two sticks sleeps `[0.5, 0.2, 0.2]`; `paint` ends with the pen up; `rosette`
  leaves 36 turtles with empty undo buffers; `round_dance` runs past 500
  frames until its bound key-press handler is called, then returns, and
  leaves 16 turtles; `sorting_animate` shelves ten blocks; `tree` leaves
  1,024 turtles; `two_canvases`, started from the viewer on a stand-in `TK`,
  creates one Tk root and two canvases, and the viewer's STOP destroys
  neither and clears neither.
* Lib/turtledemo differs across v3.10.19, v3.11.14, v3.12.12, v3.13.11 and
  v3.14.2 only in docstrings, the viewer's menus and layout, and `clock`,
  which from 3.12 rewrites the date only when the day changes; none of those
  moves a bound here.
* Every fenced Python block runs in its own subprocess on the recording
  screen, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The viewer's window, menus, text colouring and event loop need a display:
  `DemoWindow()` and `python -m turtledemo` are not run, and their O(e) is
  read from `makeLoadDemoMenu()`, which calls `getExampleEntries()` once.
  The `DemoWindow` methods that build or configure widgets - `onResize`,
  `makeTextFrame`, `makeGraphFrame`, `set_txtsize`, `decrease_size`,
  `increase_size`, `update_mousewheel`, `configGUI`, `makeLoadDemoMenu`
  (one menu entry per demo), `makeFontMenu` and `makeHelpMenu` - and
  `refreshCanvas` and `clearCanvas`, which clear the screen at the turtle
  page's cost, are left off the page. That Tk processes a click only inside `update()` is Tk's
  behaviour, stood in for here by delivering STOP from the recording canvas.
* The demos' other functions - drawing primitives such as `kite()`,
  `dart()`, `jump()`, `hand()`, `yin()` and the `bytedesign` pieces,
  `lindenmayer.draw()`, `chaos.plot()`, `nim.computerzug()` and the event
  callbacks - are left off the page and priced only through their demo's
  `main()`, which calls them with fixed arguments.
* The recursion space of `hilbert()` and `hanoi()` is observed as stack
  depth; that the other recursive helpers keep O(L) frames is read
  from their source. The Penrose space bound follows from the tile count
  observed; φ² as the limit of its growth is the tiling's mathematics, and
  the counts depend on `round()` of floating-point positions.
* `GravSys.start()`'s O(p²) per step is observed as `pos()` calls; the
  arithmetic on `Vec2D` is not counted separately, and the step count is not
  varied beyond the two sizes above.
* The `colormixer` drag is driven by calling `ColorTurtle.shift()`, not
  through a bound item handler: the recording canvas keeps canvas-level
  bindings only, and `unbind()` removes nothing from them.
* Timing and allocation vary one input shape each: the snake rules, and the
  sorts' sorted, reversed and three shuffled shelves.
"""

from __future__ import annotations

import builtins
import importlib
import itertools
import math
import os
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import turtle
import turtledemo
import turtledemo.__main__ as viewer
import types
import zlib
from collections.abc import Callable, Iterator
from turtledemo import (
    forest,
    fractalcurves,
    lindenmayer,
    minimal_hanoi,
    penrose,
    planet_and_moon,
    rosette,
    sorting_animate,
    tree,
)
from typing import Any

import pytest

from tests.test_turtle_complexity import FakeCanvas

# The module's private singletons, and the demos, seen without their inferred types.
TurtleClass: Any = turtle.Turtle
TurtleScreenClass: Any = turtle.TurtleScreen
RawTurtleClass: Any = turtle.RawTurtle
sa: Any = sorting_animate
pr: Any = penrose

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "turtledemo.md"
EXPECTED_BLOCKS = 6
DEMOS = [
    "bytedesign",
    "chaos",
    "clock",
    "colormixer",
    "forest",
    "fractalcurves",
    "lindenmayer",
    "minimal_hanoi",
    "nim",
    "paint",
    "peace",
    "penrose",
    "planet_and_moon",
    "rosette",
    "round_dance",
    "sorting_animate",
    "tree",
    "two_canvases",
    "yinyang",
]


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


def stack_depth() -> int:
    frame = sys._getframe()  # noqa: SLF001
    depth = 0
    while frame is not None:
        depth += 1
        frame = frame.f_back  # type: ignore[assignment]
    return depth


class DemoCanvas(FakeCanvas):
    """The recording canvas, taking any colour name and keeping timer callbacks.

    `on_update` stands in for the Tk events a real `update()` would process,
    and `bindings` keeps each event handler bound on the canvas.
    """

    def __init__(self) -> None:
        super().__init__()
        self.timers: list[tuple[int, Callable[[], Any]]] = []
        self.on_update: Callable[[], None] | None = None
        self.bindings: dict[str, Callable[[Any], Any]] = {}

    def bind(self, *args: Any, **options: Any) -> None:
        if len(args) >= 2 and args[1] is not None:
            self.bindings[args[0]] = args[1]

    def winfo_rgb(self, color: str) -> tuple[int, int, int]:
        try:
            return super().winfo_rgb(color)
        except Exception:
            digest = zlib.crc32(color.encode())
            return digest & 0xFFFF, (digest >> 8) & 0xFFFF, (digest >> 16) & 0xFFFF

    def after(self, ms: int, func: Callable[[], Any] | None = None) -> None:
        if func is None:
            self.pauses.append(ms)
        else:
            self.timers.append((ms, func))

    def update(self) -> None:
        super().update()
        if self.on_update is not None:
            self.on_update()


class DemoScreen(turtle._Screen):  # noqa: SLF001
    """The singleton screen on a `DemoCanvas`, with the Tk-only calls stubbed."""

    mainloops = 0

    def __init__(self) -> None:
        TurtleScreenClass.__init__(self, DemoCanvas())

    @property
    def canvas(self) -> DemoCanvas:
        return self.cv  # type: ignore[attr-defined,no-any-return]

    def mainloop(self) -> None:
        DemoScreen.mainloops += 1

    def exitonclick(self) -> None:
        pass

    def bye(self) -> None:
        pass


def install_demo_screen() -> DemoScreen:
    """Make `Screen()` and `Turtle()` work on a fresh recording canvas."""
    TurtleScreenClass._RUNNING = True
    screen = DemoScreen()
    TurtleClass._screen = screen
    TurtleClass._pen = None
    return screen


@pytest.fixture(autouse=True)
def _restore_module_state() -> Iterator[None]:
    screens = list(RawTurtleClass.screens)
    yield
    TurtleScreenClass._RUNNING = True
    TurtleClass._screen = None
    TurtleClass._pen = None
    RawTurtleClass.screens[:] = screens


class Commands:
    """Counts moves, turns and clones made by every turtle."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.moves = self.turns = self.clones = 0
        self.max_depth = 0
        self.min_depth = sys.maxsize
        goto, rotate, clone = RawTurtleClass._goto, RawTurtleClass._rotate, RawTurtleClass.clone

        def counting_goto(pen: Any, *args: Any) -> Any:
            self.moves += 1
            depth = stack_depth()
            self.max_depth = max(self.max_depth, depth)
            self.min_depth = min(self.min_depth, depth)
            return goto(pen, *args)

        def counting_rotate(pen: Any, *args: Any) -> Any:
            self.turns += 1
            return rotate(pen, *args)

        def counting_clone(pen: Any) -> Any:
            self.clones += 1
            return clone(pen)

        monkeypatch.setattr(RawTurtleClass, "_goto", counting_goto)
        monkeypatch.setattr(RawTurtleClass, "_rotate", counting_rotate)
        monkeypatch.setattr(RawTurtleClass, "clone", counting_clone)

    def reset(self) -> None:
        self.moves = self.turns = self.clones = 0
        self.max_depth = 0
        self.min_depth = sys.maxsize


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> Commands:
    return Commands(monkeypatch)


@pytest.fixture
def screen() -> DemoScreen:
    screen = install_demo_screen()
    screen.tracer(0)
    return screen


RUNNER = (
    "import sys; sys.path.insert(0, {root!r}); "
    "from tests.test_turtledemo_complexity import install_demo_screen; install_demo_screen(); "
    "import runpy; runpy.run_path('block.py', run_name='__main__')"
)


def _run(code: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestImportingDrawsNothing:
    """`import turtledemo` | O(1); `import turtledemo.<demo>` draws nothing and
    opens no window; `python -m turtledemo.<demo>` runs `main()`, then the
    event loop."""

    def test_the_package_defines_no_public_name(self, tmp_path: pathlib.Path) -> None:
        code = (
            "import turtledemo\n"
            "assert [n for n in vars(turtledemo) if not n.startswith('_')] == []\n"
            "assert 'viewer' in turtledemo.__doc__\n"
        )

        result = _run(code, tmp_path)

        assert result.returncode == 0, result.stderr

    def test_importing_every_demo_opens_nothing(self, tmp_path: pathlib.Path) -> None:
        code = textwrap.dedent(
            f"""
            import importlib, tkinter, turtle
            def refuse(*args, **kwargs):
                raise AssertionError("a Tk root was created at import")
            tkinter.Tk = refuse
            for name in {DEMOS!r}:
                importlib.import_module("turtledemo." + name)
            assert turtle.Turtle._screen is None
            assert turtle._Screen._root is None
            assert turtle.Turtle._pen is None
            """
        )

        result = _run(code, tmp_path)

        assert result.returncode == 0, result.stderr

    def test_running_a_demo_as_a_script_draws_then_enters_the_loop(
        self, tmp_path: pathlib.Path
    ) -> None:
        code = RUNNER.format(root=str(PAGE.parent.parent.parent)).replace(
            "runpy.run_path('block.py', run_name='__main__')",
            "from tests.test_turtledemo_complexity import DemoScreen; import turtle; "
            "runpy.run_module('turtledemo.yinyang', run_name='__main__'); "
            "assert DemoScreen.mainloops == 1, DemoScreen.mainloops; "
            "assert len(turtle.Screen().cv.items) > 5",
        )

        result = _run(code, tmp_path)

        assert result.returncode == 0, result.stderr


class Widget:
    """Records what the viewer asks of a Tk widget."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def config(self, **options: Any) -> None:
        self.calls.append(options)

    def delete(self, *args: Any) -> None:
        self.calls.append(("delete", *args))

    def insert(self, index: str, text: str) -> None:
        self.calls.append(("insert", index, text))

    def title(self, text: str) -> None:
        self.calls.append(("title", text))


def headless_viewer(screen: DemoScreen) -> Any:
    """A `DemoWindow` without its Tk widgets, on the recording screen."""
    window: Any = viewer.DemoWindow.__new__(viewer.DemoWindow)
    window.root = Widget()
    window.text = Widget()
    window.start_btn, window.stop_btn, window.clear_btn = Widget(), Widget(), Widget()
    window.output_lbl = Widget()
    window.screen = screen
    window.canvas = window.scanvas = screen.canvas  # `scanvas` on 3.10
    window.dirty = False
    window.exitflag = False
    return window


def counting_clears(monkeypatch: pytest.MonkeyPatch, screen: DemoScreen) -> list[int]:
    clears: list[int] = []
    original = screen.clear

    def clear() -> None:
        clears.append(1)
        original()

    monkeypatch.setattr(screen, "clear", clear)
    return clears


class TestTheViewer:
    """`getExampleEntries()` | O(e); `loadfile()` | O(I + K² + c); `startDemo()`
    runs `main()` to completion; `stopIt()` stops it at its next command."""

    def test_the_menu_lists_the_nineteen_demos(self) -> None:
        assert sorted(viewer.getExampleEntries()) == DEMOS

    def test_it_lists_the_directory_on_every_call(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in ("a.py", "_b.py", "c.txt", "d.py"):
            (tmp_path / name).write_text("", encoding="utf-8")
        listings: list[str] = []
        listdir = os.listdir

        def counting_listdir(path: Any) -> list[str]:
            listings.append(path)
            return listdir(path)

        monkeypatch.setattr(viewer, "demo_dir", str(tmp_path))
        monkeypatch.setattr(os, "listdir", counting_listdir)

        assert viewer.getExampleEntries() == [
            n[:-3] for n in listdir(tmp_path) if n in ("a.py", "d.py")
        ]
        assert sorted(viewer.getExampleEntries()) == ["a", "d"]
        assert listings == [str(tmp_path)] * 2

    def test_it_keeps_the_directory_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(os, "listdir", lambda path: ["z.py", "a.py", "m.py"])

        assert viewer.getExampleEntries() == ["z", "a", "m"]

    def test_loadfile_imports_once_and_shows_the_whole_source(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = (
            "import sys\n"
            "sys.modules['builtins'].__dict__.setdefault('_td_loads', []).append(1)\n"
            + "# padding\n" * 500
            + "def main():\n    return 'ok'\n"
        )
        (tmp_path / "td_probe.py").write_text(source, encoding="utf-8")
        monkeypatch.setattr(turtledemo, "__path__", [*turtledemo.__path__, str(tmp_path)])
        monkeypatch.delitem(sys.modules, "turtledemo.td_probe", raising=False)
        loads: list[int] = []
        monkeypatch.setattr(builtins, "_td_loads", loads, raising=False)
        screen = install_demo_screen()
        window = headless_viewer(screen)
        clears = counting_clears(monkeypatch, screen)

        try:
            window.loadfile("td_probe")
            first = window.module
            window.loadfile("td_probe")
        finally:
            sys.modules.pop("turtledemo.td_probe", None)

        assert loads == [1], "the demo's top level ran more than once"
        assert window.module is first
        inserted = [call for call in window.text.calls if call[0] == "insert"]
        assert [call[2] for call in inserted] == [source] * 2
        assert clears == [], "a clean viewer has nothing to clear"

        window.dirty = True
        window.loadfile("td_probe")
        assert clears == [1], "after a demo has run, loading clears the screen"

    def test_start_runs_main_to_completion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        screen = install_demo_screen()
        window = headless_viewer(screen)
        clears = counting_clears(monkeypatch, screen)
        ran: list[str] = []

        def main() -> str:
            pen = turtle.Turtle()
            pen.forward(10)
            ran.append("main")
            return "finished"

        window.module = types.SimpleNamespace(main=main)

        window.startDemo()

        assert ran == ["main"]
        assert window.state == viewer.DONE
        assert window.output_lbl.calls[-1]["text"] == "finished"
        assert clears == [1]

        window.startDemo()  # the viewer is dirty now: one more clear before the usual one
        assert clears == [1, 1, 1]

    def test_an_event_driven_demo_returns_at_once_and_stop_clears_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        screen = install_demo_screen()
        window = headless_viewer(screen)
        window.module = types.SimpleNamespace(main=lambda: "EVENTLOOP")

        window.startDemo()
        assert window.state == viewer.EVENTDRIVEN
        clears = counting_clears(monkeypatch, screen)

        window.stopIt()

        assert clears == [1]
        assert window.output_lbl.calls[-1]["text"] == "STOPPED!"

    def test_stop_while_running_does_not_clear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        screen = install_demo_screen()
        window = headless_viewer(screen)
        clears = counting_clears(monkeypatch, screen)

        window.stopIt()

        assert clears == []
        assert TurtleScreenClass._RUNNING is False

    def test_stop_takes_effect_at_the_next_command_after_a_frame(self) -> None:
        screen = install_demo_screen()
        window = headless_viewer(screen)
        done: list[int] = []

        def main() -> str:
            pen = turtle.Turtle()
            pen.speed(0)
            for index in range(20):
                if index == 5:
                    # The click arrives with the next frame, as Tk would deliver it.
                    screen.canvas.on_update = window.stopIt
                pen.forward(10)
                done.append(index)
            return "finished"

        window.module = types.SimpleNamespace(main=main)

        window.startDemo()

        assert done == [0, 1, 2, 3, 4, 5], "the move whose frame saw STOP completes"
        assert window.state == viewer.DONE
        assert window.output_lbl.calls[-1]["text"] == "stopped!"

    def test_under_tracer_0_only_update_delivers_and_checks_stop(self) -> None:
        screen = install_demo_screen()
        window = headless_viewer(screen)
        done: list[int] = []
        frames: list[int] = []

        def main() -> str:
            pen = turtle.Turtle()
            screen.tracer(0)
            screen.canvas.updates = 0
            screen.canvas.on_update = window.stopIt
            for index in range(50):
                pen.forward(10)
                done.append(index)
            frames.append(screen.canvas.updates)
            screen.update()  # the click arrives here
            pen.forward(10)  # a move under tracer(0) does not check for it
            done.append(50)
            screen.update()  # this one raises
            done.append(51)
            return "finished"

        window.module = types.SimpleNamespace(main=main)

        window.startDemo()

        assert frames == [0], "moves under tracer(0) redraw nothing"
        assert done == list(range(51))
        assert window.output_lbl.calls[-1]["text"] == "stopped!"


class TestHilbertAndKoch:
    """`hilbert()` and `fractal()` | O(4^L) | O(L); `fractalgon()` | O(v·4^L)."""

    def test_hilbert_moves_and_turns(self, screen: DemoScreen, commands: Commands) -> None:
        depths = []
        for level in range(1, 6):
            pen: Any = fractalcurves.CurvesTurtle()
            commands.reset()

            pen.hilbert(5, level, 1)

            assert commands.moves == 4**level - 1
            assert commands.turns == 4 * (4**level - 1) // 3
            depths.append(commands.max_depth)

        steps = {later - earlier for earlier, later in itertools.pairwise(depths)}
        assert steps == {1}, f"recursion depth per level: {depths}"

    def test_fractal_moves(self, screen: DemoScreen, commands: Commands) -> None:
        for depth in range(5):
            pen: Any = fractalcurves.CurvesTurtle()
            commands.reset()

            pen.fractal(100, depth, 1)

            assert commands.moves == 4**depth

    def test_fractalgon_is_one_fractal_per_side(
        self, screen: DemoScreen, commands: Commands
    ) -> None:
        pen: Any = fractalcurves.CurvesTurtle()
        commands.reset()

        pen.fractalgon(5, 100, 2, 1)

        assert commands.moves == 5 * 4**2 + 2


class TestTreesCloneTurtles:
    """`tree.tree()` | O(q·2^L), and never yields; `forest.tree()` | O(b^L),
    one branch per `next()`; every clone stays on the screen."""

    @pytest.mark.parametrize(("length", "levels"), [(50, 7), (200, 10)])
    @pytest.mark.parametrize("pens", [1, 2])
    def test_tree_doubles_the_pens_per_level(
        self, screen: DemoScreen, commands: Commands, length: int, levels: int, pens: int
    ) -> None:
        plist: list[Any] = []
        for _ in range(pens):
            pen: Any = turtle.Turtle()
            pen.setundobuffer(None)
            plist.append(pen)
        commands.reset()

        growth = tree.tree(plist, length, 65, 0.6375)
        assert (commands.moves, commands.clones) == (0, 0), "building the generator drew"

        assert list(growth) == []
        assert commands.moves == commands.clones == pens * (2**levels - 1)
        assert len(screen.turtles()) == pens * 2**levels

    @pytest.mark.parametrize("branches", [2, 3])
    @pytest.mark.parametrize("level", [2, 3, 4, 5])
    def test_forest_draws_one_branch_per_step(
        self, screen: DemoScreen, commands: Commands, branches: int, level: int
    ) -> None:
        screen.colormode(255)
        pen: Any = turtle.Turtle(undobuffersize=1)
        branchlist = [(45, 0.69), (0, 0.65), (-45, 0.71)][:branches]
        commands.reset()

        growth = forest.tree([pen], 80, level, 0.1, [branchlist])
        assert (commands.moves, commands.clones) == (0, 0), "building the generator drew"

        steps = []
        while True:
            before = (commands.moves, commands.clones)
            try:
                next(growth)
            except StopIteration:
                break
            finally:
                steps.append((commands.moves - before[0], commands.clones - before[1]))

        yields = len(steps) - 1
        assert yields == sum(branches**j for j in range(level))
        assert commands.clones == sum(branches**j for j in range(1, level + 1))
        assert commands.moves == sum(branches**j * (level - j) for j in range(level))
        assert all(moves <= level and clones <= branches for moves, clones in steps)
        assert len(screen.turtles()) == 1 + commands.clones
        assert commands.max_depth - commands.min_depth == level - 1, "nested generators"

    def test_stop_ends_one_forest_tree_and_the_others_go_on(self) -> None:
        screen = install_demo_screen()
        window = headless_viewer(screen)
        window.module = forest
        frames = itertools.count()

        def click_stop_once() -> None:
            if next(frames) == 30:
                window.stopIt()

        screen.canvas.on_update = click_stop_once

        window.startDemo()

        assert window.state == viewer.DONE
        assert window.output_lbl.calls[-1]["text"].startswith("runtime:"), "main() returned"
        assert 1 + 3 < len(screen.turtles()) < 1_713, "one tree ended early, the rest grew"


class TestHanoi:
    """`hanoi(n, ...)` | O(2^d) | O(d)."""

    def test_disc_moves_and_depth(
        self, screen: DemoScreen, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        towers: Any = minimal_hanoi
        pushes: list[int] = []
        depths: list[int] = []
        push = towers.Tower.push

        def counting_push(tower: Any, disc: Any) -> None:
            pushes.append(1)
            depths.append(stack_depth())
            push(tower, disc)

        for discs in range(1, 7):  # Disc colours are defined up to 6
            pegs = [towers.Tower(-250), towers.Tower(0), towers.Tower(250)]
            for size in range(discs, 0, -1):
                pegs[0].push(towers.Disc(size))
            monkeypatch.setattr(towers.Tower, "push", counting_push)
            pushes.clear()
            depths.clear()

            towers.hanoi(discs, *pegs)

            monkeypatch.setattr(towers.Tower, "push", push)
            assert len(pushes) == 2**discs - 1
            assert len(pegs[2]) == discs
            assert max(depths) - min(depths) == discs - 1


class Block:
    """A stand-in for `sorting_animate.Block` that counts moves and size reads."""

    moves = 0
    reads = 0

    def __init__(self, size: int) -> None:
        self._size = size
        self.x = 0.0

    @property
    def size(self) -> int:
        Block.reads += 1
        return self._size

    def shapesize(self) -> tuple[float, float, int]:
        return (self._size * 1.5, 1.5, 2)

    def pos(self) -> tuple[float, float]:
        return (self.x, 0.0)

    def setx(self, x: float) -> None:
        Block.moves += 1
        self.x = x

    def sety(self, y: float) -> None:
        Block.moves += 1

    def glow(self) -> None:
        pass

    def unglow(self) -> None:
        pass


def shelf_of(sizes: list[int]) -> Any:
    shelf = sa.Shelf(-200)
    for size in sizes:
        shelf.push(Block(size))
    Block.moves = Block.reads = 0
    return shelf


def sort_cost(sort: str, sizes: list[int]) -> tuple[int, int]:
    """Moves and size reads of one sort; asserts the shelf ends sorted."""
    shelf = shelf_of(sizes)
    if sort == "qsort":
        sa.qsort(shelf, 0, len(shelf) - 1)
    else:
        getattr(sa, sort)(shelf)
    assert [block._size for block in shelf] == sorted(sizes)
    return Block.moves, Block.reads


class TestSortingOnAShelf:
    """`Shelf.pop()`/`insert()` | O(n − key); `isort` and `ssort` | O(n²);
    `qsort` | O(n² log n) average, O(n³) worst, in moves."""

    def test_pop_and_insert_slide_every_later_block(self) -> None:
        for key in (0, 3, 9):
            shelf = shelf_of(list(range(10)))
            block = shelf.pop(key)
            assert Block.moves == 1 + (9 - key), f"pop({key})"

            Block.moves = 0
            shelf.insert(key, block)
            assert Block.moves == 2 + (9 - key), f"insert({key})"

    def test_pop_copies_the_tail_of_the_shelf(self) -> None:
        count = 200_000
        early = shelf_of(list(range(count)))
        late = shelf_of(list(range(count)))

        peaks = [peak_bytes(lambda: early.pop(0)), peak_bytes(lambda: late.pop(count - 1))]

        assert peaks[0] > 1_600_000, f"pop(0) over {count} blocks peaked at {peaks[0]}"
        assert peaks[1] * 20 < peaks[0], f"pop() of the last block peaked at {peaks[1]}"

    def test_isort_is_quadratic_even_when_sorted(self) -> None:
        small, _ = sort_cost("isort", list(range(40)))
        large, _ = sort_cost("isort", list(range(160)))

        assert large > small * 12, f"4x the sorted blocks: {small} -> {large} moves"

    def test_ssort_compares_every_pair_and_moves_nothing_when_sorted(self) -> None:
        for count in (10, 40):
            moves, reads = sort_cost("ssort", list(range(count)))
            assert (moves, reads) == (0, count * (count - 1))

            _, reads = sort_cost("ssort", list(range(count))[::-1])
            assert reads == count * (count - 1)

    def test_qsort_moves_are_cubic_on_a_reversed_shelf(self) -> None:
        small, _ = sort_cost("qsort", list(range(80))[::-1])
        large, _ = sort_cost("qsort", list(range(160))[::-1])

        assert large > small * 6, f"2x the reversed blocks: {small} -> {large} moves"

    def test_qsort_moves_grow_as_n_squared_log_n_on_shuffles(self) -> None:
        def average(count: int) -> float:
            total = 0
            for seed in range(3):
                sizes = random.Random(seed).sample(range(count), count)
                total += sort_cost("qsort", sizes)[0]
            return total / 3

        ratio = average(800) / average(50)

        assert 300 < ratio < 1_000, f"16x the shuffled blocks cost x{ratio:.0f} moves"

    @pytest.mark.parametrize("backwards", [False, True])
    def test_qsort_compares_quadratically_on_an_ordered_shelf(self, backwards: bool) -> None:
        def ordered(count: int) -> list[int]:
            return list(range(count))[:: -1 if backwards else 1]

        _, small = sort_cost("qsort", ordered(40))
        _, large = sort_cost("qsort", ordered(160))

        assert large > small * 12, f"4x the ordered blocks: {small} -> {large} size reads"


SNAKE = {"b": "b+f+b--f--b+f+b"}


class TestLindenmayer:
    """`replace(seq, rules, n)` | O(M) | O(M)."""

    def test_the_snake_grows_about_fourfold(self) -> None:
        lengths = [len(lindenmayer.replace("b--f--b--f", SNAKE, n)) for n in range(5)]

        assert lengths == [10, 38, 150, 598, 2390]

    def test_the_peak_follows_the_result(self) -> None:
        peaks = [
            peak_bytes(lambda n=n: lindenmayer.replace("b--f--b--f", SNAKE, n)) for n in (6, 8)
        ]

        assert peaks[1] > peaks[0] * 10, f"16x the characters peaked at {peaks}"

    @pytest.mark.timing
    def test_appending_is_linear_in_the_result(self) -> None:
        durations = [
            best_ns(lambda n=n: lindenmayer.replace("b--f--b--f", SNAKE, n)) for n in (6, 8)
        ]
        ratio = durations[1] / durations[0]

        assert ratio < 40, f"16x the characters cost x{ratio:.1f}; quadratic would be ~256x"


class CountingDict(dict[Any, bool]):
    """`penrose.tiledict`, counting every write the recursion makes."""

    writes = 0

    def __setitem__(self, key: Any, value: bool) -> None:
        CountingDict.writes += 1
        super().__setitem__(key, value)


def inflate(fun: Callable[[float, int], None], level: int) -> tuple[int, int]:
    """Recursion leaves and distinct tiles of one `sun()` or `star()`."""
    CountingDict.writes = 0
    pr.tiledict = CountingDict()
    turtle.home()
    fun(300, level)
    return CountingDict.writes, len(pr.tiledict)


class TestPenroseInflation:
    """`inflatekite()`/`inflatedart()` | O((2 + √2)^L) | O(φ^(2L)); `draw()` | O(z)."""

    @pytest.mark.parametrize("name", ["sun", "star"])
    def test_the_recursion_outgrows_the_tiling(self, screen: DemoScreen, name: str) -> None:
        fun = getattr(pr, name)
        assert inflate(fun, 0) == (5, 5), "five inflations"

        leaves_7, tiles_7 = inflate(fun, 7)
        leaves_8, tiles_8 = inflate(fun, 8)

        assert 3.40 < leaves_8 / leaves_7 < 3.43, (leaves_7, leaves_8)
        assert 2.5 < tiles_8 / tiles_7 < 3.0, (tiles_7, tiles_8)
        assert leaves_8 > tiles_8 * 5, (leaves_8, tiles_8)
        assert (2 + math.sqrt(2)) ** 8 < leaves_8 / 5 * 2

    def test_draw_stamps_each_tile_once(self, screen: DemoScreen) -> None:
        pr.start()
        screen.tracer(0)
        _, tiles = inflate(pr.sun, 4)
        before = len(screen.canvas.items)

        pr.draw(300, 4)

        assert len(screen.canvas.items) - before == tiles


class TestRosette:
    """`mn_eck(p, ne, sz)` | O(t²) | O(t)."""

    @pytest.mark.parametrize("count", [4, 8, 16])
    def test_every_turtle_takes_every_step(
        self, screen: DemoScreen, commands: Commands, count: int
    ) -> None:
        pen: Any = turtle.Turtle()
        commands.reset()

        rosette.mn_eck(pen, count, 19)

        assert (commands.moves, commands.clones) == (count**2, count - 1)
        assert len(screen.turtles()) == count


class TestGravitySteps:
    """`GravSys.start()` | O(p²) per step | O(p) per step."""

    @staticmethod
    def system(bodies: int) -> Any:
        grav: Any = planet_and_moon
        system = grav.GravSys()
        for index in range(bodies):
            angle = 2 * math.pi * index / bodies
            position = turtle.Vec2D(200 * math.cos(angle), 200 * math.sin(angle))
            grav.Star(1000, position, turtle.Vec2D(0, 1), system, "circle")
        system.init()
        return system

    def test_one_step_reads_every_pair(
        self, screen: DemoScreen, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reads: list[int] = []
        pos = RawTurtleClass.pos

        def counting_pos(pen: Any) -> Any:
            reads.append(1)
            return pos(pen)

        counts = []
        for bodies in (6, 12):
            system = self.system(bodies)
            monkeypatch.setattr(RawTurtleClass, "pos", counting_pos)
            reads.clear()
            for body in system.planets:
                body.step()
            counts.append(len(reads))
            monkeypatch.setattr(RawTurtleClass, "pos", pos)

        assert counts[1] > counts[0] * 3.5, f"2x the bodies: {counts} pos() calls"

    def test_the_trail_stays_on_the_canvas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        points = []
        for steps in (420, 4_200):
            fresh = install_demo_screen()
            fresh.tracer(1, 0)
            canvas = fresh.canvas
            monkeypatch.setattr(
                planet_and_moon, "range", lambda _n, s=steps: builtins.range(s), raising=False
            )
            system = self.system(2)
            system.start()
            points.append(sum(len(coords) for _, coords in canvas.items.values()))

        assert points[1] > points[0] * 8, f"10x the steps left {points} coordinates"


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []

    def sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr(time, "sleep", sleep)
    for module in (fractalcurves, penrose, rosette):
        monkeypatch.setattr(module, "sleep", sleep)
    return recorded


def run_main(name: str) -> tuple[Any, DemoScreen, Any]:
    screen = install_demo_screen()
    module: Any = importlib.import_module("turtledemo." + name)
    return module.main(), screen, module


class TestDemos:
    """Every `main()` returns what its row says, after the sleeps it lists."""

    @pytest.mark.parametrize(
        ("name", "returned"),
        [
            ("colormixer", "EVENTLOOP"),
            ("minimal_hanoi", "EVENTLOOP"),
            ("nim", "EVENTLOOP"),
            ("paint", "EVENTLOOP"),
            ("sorting_animate", "EVENTLOOP"),
            ("chaos", "Done!"),
            ("peace", "Done!"),
            ("planet_and_moon", "Done!"),
            ("yinyang", "Done!"),
        ],
    )
    def test_the_fixed_return_values(self, sleeps: list[float], name: str, returned: str) -> None:
        result, _, _ = run_main(name)

        assert result == returned
        assert sleeps == []

    @pytest.mark.parametrize(
        ("name", "pattern", "slept"),
        [
            ("bytedesign", r"runtime: \d+\.\d+ sec\.", []),
            ("forest", r"runtime: \d+\.\d+ sec\.", []),
            ("fractalcurves", r"Hilbert: \d+\.\d+sec\. Koch: \d+\.\d+sec\.", [3]),
            ("lindenmayer", r"Done!", [3]),
            ("rosette", r"runtime: \d+\.\d+ sec", [1]),
            ("tree", r"done: \d+\.\d+ sec\.", []),
        ],
    )
    def test_the_timed_demos(
        self, sleeps: list[float], name: str, pattern: str, slept: list[float]
    ) -> None:
        result, _, _ = run_main(name)

        assert re.fullmatch(pattern, result), result
        assert sleeps == slept

    def test_bytedesign_updates_by_hand_under_tracer_0(self, sleeps: list[float]) -> None:
        screen = install_demo_screen()
        updates: list[int] = []
        original = screen.update

        def update() -> None:
            if screen.tracer() == 0:
                updates.append(1)
            original()

        screen.update = update  # type: ignore[method-assign]
        importlib.import_module("turtledemo.bytedesign").main()

        assert len(updates) >= 25, f"{len(updates)} updates under tracer(0)"

    def test_chaos_rescales_101_times(
        self, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[int] = []
        original = TurtleScreenClass.setworldcoordinates

        def counting(screen: Any, *args: Any) -> None:
            calls.append(1)
            original(screen, *args)

        monkeypatch.setattr(TurtleScreenClass, "setworldcoordinates", counting)
        run_main("chaos")

        assert len(calls) == 101

    def test_clock_ticks_every_100_ms(self, sleeps: list[float]) -> None:
        result, screen, _ = run_main("clock")

        assert result == "EVENTLOOP"
        assert [ms for ms, _ in screen.canvas.timers] == [100]
        screen.canvas.timers.pop()[1]()
        assert [ms for ms, _ in screen.canvas.timers] == [100]

    def test_a_colormixer_drag_recolours_the_background(self, sleeps: list[float]) -> None:
        _, screen, module = run_main("colormixer")
        colours: list[tuple[Any, ...]] = []
        screen.bgcolor = lambda *args: colours.append(args)  # type: ignore[method-assign]

        module.red.shift(0, 0.9)

        assert colours == [(0.9, 0.5, 0.5)]

    def test_forest_leaves_every_turtle(self, sleeps: list[float]) -> None:
        _, screen, _ = run_main("forest")

        trees = [(3, 6), (2, 7), (3, 5)]
        clones = sum(sum(b**j for j in range(1, level + 1)) for b, level in trees)
        assert len(screen.turtles()) == 1 + len(trees) + clones == 1_713

    def test_minimal_hanoi_moves_six_discs_on_space(self, sleeps: list[float]) -> None:
        _, screen, module = run_main("minimal_hanoi")
        assert [len(peg) for peg in (module.t1, module.t2, module.t3)] == [6, 0, 0]

        screen.canvas.bindings["<KeyRelease-space>"](None)

        assert [len(peg) for peg in (module.t1, module.t2, module.t3)] == [0, 0, 6]

    def test_nim_builds_93_sticks_and_the_reply_sleeps_per_stick(self, sleeps: list[float]) -> None:
        screen = install_demo_screen()
        nim: Any = importlib.import_module("turtledemo.nim")
        game = nim.Nim(screen)
        assert len(game.view.sticks) == 93

        game.model.setup()
        game.model.sticks = [7, 5, 3]
        game.controller.notify_move(0, 0)  # leaves 0, 5, 3: the reply takes two from row 1

        assert game.model.sticks == [0, 3, 3]
        assert sleeps == [0.5, 0.2, 0.2]

    def test_paint_ends_with_the_pen_up(self, sleeps: list[float]) -> None:
        run_main("paint")

        assert turtle.isdown() is False

    def test_penrose_holds_every_level_for_two_seconds(
        self,
        sleeps: list[float],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(penrose, "clock", lambda: 0.0)

        result, _, _ = run_main("penrose")

        assert result == "Done"
        assert sleeps == [2.0] * 17
        assert sum(sleeps) == 34
        assert capsys.readouterr().out.count("pieces.") == 17

    def test_rosette_undoes_everything(self, sleeps: list[float]) -> None:
        _, screen, _ = run_main("rosette")

        assert len(screen.turtles()) == 36
        assert all(pen.undobufferentries() == 0 for pen in screen.turtles())

    def test_round_dance_runs_until_a_key(self, sleeps: list[float]) -> None:
        screen = install_demo_screen()
        module: Any = importlib.import_module("turtledemo.round_dance")
        frames = itertools.count()

        def press_a_key_eventually() -> None:
            if next(frames) == 500:
                screen.canvas.bindings["<KeyPress>"](None)

        screen.canvas.on_update = press_a_key_eventually

        assert module.main() == "DONE!"
        assert next(frames) > 500, "main() returned before the key"
        assert len(screen.turtles()) == 16

    def test_sorting_animate_shelves_ten_blocks(self, sleeps: list[float]) -> None:
        _, _, module = run_main("sorting_animate")

        assert [block.size for block in module.s] == [4, 2, 8, 9, 1, 5, 10, 3, 7, 6]

    def test_tree_leaves_1024_turtles(self, sleeps: list[float]) -> None:
        _, screen, _ = run_main("tree")

        assert len(screen.turtles()) == 1_024

    def test_two_canvases_opens_a_window_it_does_not_close(
        self, sleeps: list[float], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        roots: list[Any] = []
        canvases: list[DemoCanvas] = []

        class Root:
            destroyed = False

            def __init__(self) -> None:
                roots.append(self)

            def destroy(self) -> None:
                self.destroyed = True

        def canvas(root: Any, **options: Any) -> DemoCanvas:
            made = DemoCanvas()
            made.pack = lambda: None  # type: ignore[attr-defined]
            canvases.append(made)
            return made

        module: Any = importlib.import_module("turtledemo.two_canvases")
        monkeypatch.setattr(module, "TK", types.SimpleNamespace(Tk=Root, Canvas=canvas))

        window = headless_viewer(install_demo_screen())
        window.module = module
        window.startDemo()
        assert window.state == viewer.EVENTDRIVEN
        assert len(roots) == 1 and len(canvases) == 2
        assert all(len(made.items) > 0 for made in canvases)
        drawn = [dict(made.items) for made in canvases]

        window.stopIt()

        assert not roots[0].destroyed
        assert [dict(made.items) for made in canvases] == drawn, "STOP left that window alone"


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
    (cwd / "block.py").write_text(source, encoding="utf-8")
    return _run(RUNNER.format(root=str(PAGE.parent.parent.parent)), cwd)


class TestDocumentedExamples:
    """Each block runs in its own subprocess with the singleton screen on a
    recording canvas, so `Screen()` and `Turtle()` need no display, and
    asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "entries == [147, 595]" in s)
        mutated = source.replace("entries == [147, 595]", "entries == [147, 594]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
