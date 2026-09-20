"""Tests for docs/stdlib/turtle.md.

The page prices the module in two currencies: Python-side work on the turtle's
own lists, and frames, each a canvas redraw plus a pause. Both are settled
against a recording stand-in for the Tk canvas, which needs no display: every
`update()` and every pause it is asked for is counted, every item it creates
gets an id whose equality comparisons are counted, and the turtle module runs
its real code on top of it. List-copy and buffer costs are settled by traced
allocation, quadratic scans by comparison counts, and only four claims by a
stopwatch.

Measurement scope:

* Frames are counted as `update()` calls on the canvas and pauses as the
  milliseconds passed to `after()` without a callback. At speed 3 under
  `tracer(1)` with `delay(10)`, `forward(100)` is 9 frames and 90 ms,
  `forward(1000)` 84 frames, `right(90)` 12 frames and `circle(50)` 104
  frames for its 20 steps, and `circle(1000)` more than `circle(50)` for its
  longer edges, each circle at least four frames per step. The move formula
  `1 + ⌊|d| / (3s·1.1^s)⌋` and the turn formula `2 + ⌊|a| / 3s⌋` are
  asserted for six distance-speed pairs and five angle-speed pairs in
  standard mode and degrees, one of each negative; `setheading(270)` from 0 costs the
  frames of `right(90)`. Speed 0 makes `forward(1000)`, `right(720)` and a
  whole `circle(50)` one, one and two frames. Every pen setter, `write()`,
  `begin_fill()`, `shape()`, `onclick()`, `clearstamp()` and `clearstamps()`
  is one frame, `clear()` and `reset()` two, `end_fill()` one while filling
  and none otherwise, and `penup()` or `pendown()` one only when the state
  changes; `stamp()`, `ondrag()`, `degrees()`, `radians()` and every getter
  are none, and after `degrees(400)` a `left(100)` and after `radians()` a
  `left(π/2)` are each a quarter turn; `clear()` leaves pen, position and heading alone and `reset()`
  restores the defaults; `teleport()` is two with the pen down and one with it up;
  `home()` is the frames of its `goto()` plus those of its `setheading()`;
  `undo()` of a move is the frames of the move; `RawTurtle()` is one. Under
  `tracer(0)` a move, turn, pen change, circle and dot are 0 frames, `write()`
  is 0 from 3.10.8 and 3.11.1 and 1 on the patch releases before them, and
  `update()` is 1 with no pause; under
  `tracer(2)` two moves of 1000 are one frame with no pause and no hops.
  `delay(0)` leaves the frames and removes the pause. `update()` sets the
  shape coordinates of every turtle once, 2v values each for the 24-vertex
  turtle shape and for a registered 500-vertex one.
* The undo entry of a move holds a list equal to but not identical with the
  turtle's item list, whether or not a buffer is installed. The peak
  allocation of one `forward()` rises more than 50x from 11 items to 10,001,
  with and without a buffer, and a timing test finds it more than 10x slower.
  With 1,001 items and 100 buffered moves, the buffer holds 100 distinct
  copies of at least 1,001 ids each. One colour and width, 42 moves make a
  second line item, 84 a third and 126 a fourth; 100 moves alternating two
  colours make 100 items, and a width change with two points drawn makes one.
* `undo()` of a move at 201 items performs 20,100 id comparisons and at
  2,001 performs 2,001,000, so the ratio asserted is above 50. `clearstamp()`
  of the last stamp performs 496 comparisons at 100 stamps and 22,996 at
  10,000, the stamp list being scanned twice, so the ratio asserted is above
  30. `clearstamps()` and `reset()` perform 500 comparisons on 500 stamps,
  all still in the 1,000-slot buffer, and about 4,000,000 on 5,000, where
  each of the 4,000 stamps no longer in the buffer pays a full scan of it;
  the ratio asserted is above 30, and the m² term, which is `list.remove()`
  shifting the stamp list, is not counted.
  `setundobuffer()` allocates more than 50x more for 100,000 slots than for
  1,000, a timing test finds `undobufferentries()` more than 20x slower on
  the larger buffer and `clearstamp()` of an unknown id at one stamp, which
  varies only the buffer scan, more than 10x slower, and a 10-slot ring holds the last 10 of
  20 moves, undone back to the tenth.
* `clone()` peaks more than 100x higher for a turtle with 1,001 items and
  1,000 buffered moves than for one with 11 items and 10 moves, and more
  than 20x higher for a one-slot buffer holding a 1,000-step circle than a
  10-step one, so a slot is not one move; the clone has its own item list
  and undo buffer on the same screen.
* `end_fill()` after p moves passes 2(p + 1) coordinates in one call;
  `begin_fill()` adds one polygon item, and a second call while filling
  adds no polygon, only the line item that closing the current line makes,
  and restarts the path at one vertex; `clear()` installs a buffer of the
  size the turtle was built with, 100,000 slots after `setundobuffer(1)`; `get_poly()` is a new tuple of one vertex per
  move plus the start; `teleport()` pushes two pen entries with the pen down
  and no move entry, and while filling adds a fill item and at least one
  more entry unless `fill_gap=True`. An exception inside `fill()` ends the
  fill and propagates. `circle(1000)` records 60 moves, `circle(10)` 13,
  `circle(50, steps=6)` 6 and `circle(50, 180)` 10; a quarter circle is one
  undo entry, and undoing it restores the start position and heading.
* The first `setworldcoordinates()` from standard mode deletes the turtle's
  line and homes it; the second sets the coordinates of every canvas item
  once, halving the line's, and a timing test finds it more than 20x slower
  for one item of 2,000 points than of 200. `mode('logo')` deletes drawings the same way.
  `clear()` on the screen empties the canvas, the turtle list and the bound
  keys, unbinding each key's release and press events on the canvas,
  restores `tracer(1)` and forgets the anonymous turtle, as does building a
  `TurtleScreen`; a screen `reset()` costs three turtles three
  times the frames of one turtle's `reset()`. `bgpic()` creates one Tk image per distinct
  file name. `register_shape()` with a tuple makes a polygon shape and
  replaces a name, with a list stores the list, which `shape()` then fails
  on, and `getshapes()` is sorted. A hidden turtle's shape item receives no
  coordinates during a move. `onkey()` and a keyed `onkeypress()` keep one
  entry per key, and a keyless `onkeypress(None)` removes none. `stamp()`
  sets 2v coordinates on its new item, 48 for the turtle shape and 1,000
  for a registered 500-vertex one, at the turtle's position. Undoing a
  `write()` or a `dot()` deletes its items and leaves the item list as it
  was. `no_animation()` exiting to `tracer(0)` draws nothing.
* `save()`, `fill()`, `poly()`, `no_animation()` and the `PhotoImage`
  assertion of `Shape('image', data)` are guarded on 3.14, where before it a
  string that is not an existing `.gif` path is stored as given. `stamp()`,
  `clearstamp()` and `clearstamps()` raise `AttributeError` after
  `setundobuffer(None)`, while `clearstamps()` with nothing to clear does
  not; `Terminator` is raised by the first command after
  the screen stops running. `pos()` and `turtles()` return the stored objects.
  `Vec2D` arithmetic, `Shape` construction, `write_docstringdict()`, the
  module-level delegation to the anonymous turtle and `RawTurtle()` on a bare
  canvas are asserted by their results.
* Every fenced Python block runs in its own subprocess with the singleton
  screen replaced by one on the recording canvas, so `Screen()` and
  `Turtle()` work without a display and `mainloop()` returns; a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The cost of a frame itself. Tk redraws the canvas and sleeps for the
  delay; neither is observable without a display, so the page prices frames
  by count and the Tk cost by the items on the canvas from Tk's own
  behaviour. The same holds for `write()`'s text layout, image loading in
  `register_shape()` and `bgpic()`, `save()`'s PostScript rendering,
  `window_width()`, `window_height()`, `screensize()` and `bgcolor()`, which
  are single Tk calls here and cannot be priced further.
* `Screen()` building the Tk window on its first call, `Turtle()` creating
  it, `ScrolledCanvas`, `setup()`, `title()`, `bye()`, `exitonclick()`,
  `mainloop()`, `textinput()` and `numinput()` need a display or block on
  the event loop. They are exercised only as no-ops through the headless
  screen the page examples run on.
* `TNavigator`, `TPen`, `TurtleScreenBase`, `Tbuffer`, `RawTurtle.screens`,
  `config_dict()`, `readconfig()`, `read_docstrings()` and
  `getmethparlist()` are outside `__all__` and left off the page.
* Canvas item ids here are Python objects rather than Tk's small integers,
  which changes what `clone()`'s deep copy allocates per id but not how it
  scales, and comparison counts include the scans of both `in` and
  `remove()` on the stamp list.
* Timings vary items, stamps, buffer slots and coordinates one at a time on
  one input shape each. The frame formulas are not tested under world
  coordinates or other angle units, where the source scales the distance and
  converts the angle first. The screen lookup in `RawTurtle()` is a list
  membership test over screens, read from Lib/turtle.py and not scaled here;
  compound component counts and the key-list scan of `onkey()` are string
  and identity comparisons that nothing here counts, so they are not varied.
"""

from __future__ import annotations

import itertools
import math
import pathlib
import re
import runpy
import subprocess
import sys
import textwrap
import time
import tkinter
import tracemalloc
import turtle
from collections.abc import Callable, Iterator
from typing import Any

import pytest

# The module's private singletons and the Tk-typed constructors, seen without their annotations.
TurtleClass: Any = turtle.Turtle
TurtleScreenClass: Any = turtle.TurtleScreen
RawTurtleClass: Any = turtle.RawTurtle
ShapeClass: Any = turtle.Shape

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "turtle.md"
EXPECTED_BLOCKS = 8
DEFAULT_SPEED = 3
DEFAULT_DELAY = 10


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


class ItemId(int):
    """A canvas item id whose equality comparisons are counted."""

    comparisons = 0
    __hash__ = int.__hash__

    def __eq__(self, other: object) -> bool:
        ItemId.comparisons += 1
        return int.__eq__(self, other)


class FakeTk:
    """Enough of a Tcl interpreter for `tkinter.PhotoImage` to be built."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def call(self, *args: Any) -> None:
        self.calls.append(args)

    def images_created(self) -> int:
        return sum(1 for call in self.calls if call[0][:2] == ("image", "create"))


COLORS = {
    "black": (0, 0, 0),
    "white": (65535, 65535, 65535),
    "red": (65535, 0, 0),
    "blue": (0, 0, 65535),
    "green": (0, 32896, 0),
    "orange": (65535, 42405, 0),
}


class FakeCanvas:
    """A recording stand-in for a `tkinter.Canvas`.

    It keeps the items the turtle module creates, counts `update()` calls as
    frames and `after(ms)` calls as pauses, and records every `coords()` set.
    """

    def __init__(self, width: int = 400, height: int = 300) -> None:
        self._ids = itertools.count(1)
        self._width, self._height = width, height
        self.items: dict[ItemId, tuple[str, list[float]]] = {}
        self.tk = FakeTk()
        self.updates = 0
        self.pauses: list[int] = []
        self.coords_set: list[tuple[ItemId, int]] = []
        self.created: list[str] = []
        self.texts: list[str] = []
        self.unbound: list[str] = []

    def reset_log(self) -> None:
        self.updates = 0
        self.pauses = []
        self.coords_set = []
        self.created = []
        self.texts = []
        self.tk.calls = []

    def frames(self) -> int:
        return self.updates

    def paused_ms(self) -> int:
        return sum(self.pauses)

    def _new(self, kind: str, coords: tuple[float, ...]) -> ItemId:
        item = ItemId(next(self._ids))
        self.items[item] = (kind, list(coords))
        self.created.append(kind)
        return item

    def create_line(self, *coords: float, **options: Any) -> ItemId:
        return self._new("line", coords)

    def create_polygon(self, coords: tuple[float, ...], **options: Any) -> ItemId:
        return self._new("polygon", tuple(coords))

    def create_image(self, x: float, y: float, **options: Any) -> ItemId:
        return self._new("image", (x, y))

    def create_text(self, x: float, y: float, **options: Any) -> ItemId:
        self.texts.append(options.get("text", ""))
        return self._new("text", (x, y))

    def coords(self, item: Any, *coords: Any) -> list[float] | None:
        if not coords:
            return list(self.items[item][1])
        flat = list(coords[0]) if len(coords) == 1 and isinstance(coords[0], tuple) else coords
        self.items[item] = (self.items[item][0], [float(value) for value in flat])
        self.coords_set.append((item, len(flat)))
        return None

    def bbox(self, item: Any) -> tuple[int, int, int, int]:
        return (0, 0, 10, 10)

    def itemconfigure(self, item: Any, **options: Any) -> None:
        pass

    itemconfig = itemconfigure

    def tag_raise(self, item: Any) -> None:
        pass

    tag_lower = tag_raise

    def delete(self, item: Any) -> None:
        if isinstance(item, str):  # only ever "all"
            self.items.clear()
            return
        self.items.pop(item, None)

    def type(self, item: Any) -> str:
        return self.items[item][0]

    def find_all(self) -> tuple[ItemId, ...]:
        return tuple(self.items)

    def cget(self, key: str) -> Any:
        return {"width": self._width, "height": self._height, "bg": "white"}[key]

    def __getitem__(self, key: str) -> Any:
        return self.cget(key)

    def config(self, **options: Any) -> None:
        pass

    def update(self) -> None:
        self.updates += 1

    def after(self, ms: int, func: Callable[[], Any] | None = None) -> None:
        if func is None:
            self.pauses.append(ms)

    def after_idle(self, func: Callable[[], Any]) -> None:
        pass

    def bind(self, *args: Any, **options: Any) -> None:
        pass

    def unbind(self, sequence: str, *args: Any) -> None:
        self.unbound.append(sequence)

    tag_bind = bind
    tag_unbind = bind

    def focus_force(self) -> None:
        pass

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height

    def winfo_toplevel(self) -> FakeCanvas:
        return self

    def call(self, *args: Any) -> None:
        pass

    def winfo_rgb(self, color: str) -> tuple[int, int, int]:
        if color.startswith("#") and len(color) == 7:
            red, green, blue = (int(color[i : i + 2], 16) * 257 for i in (1, 3, 5))
            return red, green, blue
        try:
            return COLORS[color]
        except KeyError:
            raise tkinter.TclError(f"unknown color name {color!r}") from None

    def postscript(self) -> str:
        return "%!PS-Adobe-3.0 EPSF-3.0\n"


class HeadlessScreen(turtle._Screen):  # noqa: SLF001
    """The singleton screen on a recording canvas, with the Tk-only calls stubbed."""

    def __init__(self) -> None:
        TurtleScreenClass.__init__(self, FakeCanvas())

    def mainloop(self) -> None:
        pass

    def exitonclick(self) -> None:
        pass

    def bye(self) -> None:
        pass


def install_headless_screen() -> HeadlessScreen:
    """Make `Screen()` and `Turtle()` work without a display."""
    TurtleScreenClass._RUNNING = True
    screen = HeadlessScreen()
    TurtleClass._screen = screen
    TurtleClass._pen = None
    return screen


class Setup:
    """A screen and one turtle on a fresh recording canvas, log cleared."""

    def __init__(self, tracer: int | None = None, **options: Any) -> None:
        TurtleScreenClass._RUNNING = True
        self.canvas = FakeCanvas()
        self.screen: turtle.TurtleScreen = TurtleScreenClass(self.canvas)
        if tracer is not None:
            self.screen.tracer(tracer)
        # Typed loosely: the 3.10 stubs lack `items`, `undobuffer` and the 3.12+ methods.
        self.pen: Any = turtle.RawTurtle(self.screen, **options)
        self.canvas.reset_log()

    def add_turtle(self, **options: Any) -> Any:
        pen = turtle.RawTurtle(self.screen, **options)
        self.canvas.reset_log()
        return pen

    def frames_of(self, action: Callable[[], Any]) -> int:
        self.canvas.reset_log()
        action()
        return self.canvas.frames()


@pytest.fixture(autouse=True)
def _restore_module_state() -> Iterator[None]:
    yield
    TurtleScreenClass._RUNNING = True
    TurtleClass._screen = None
    TurtleClass._pen = None


def move_frames(distance: float, speed: int) -> int:
    """The page's formula for the frames of one move."""
    return 1 + int(abs(distance) / (3 * speed * 1.1**speed))


def turn_frames(angle: float, speed: int) -> int:
    """The page's formula for the frames of one turn."""
    return 2 + int(abs(angle) / (3 * speed))


class TestFramesPerCommand:
    """Every move, turn and pen change ends with a frame; speed cuts a move or
    turn into more frames; `tracer(0)` removes them and `update()` draws one."""

    def test_a_move_at_the_default_speed(self) -> None:
        setup = Setup()

        setup.pen.forward(100)

        assert setup.canvas.frames() == 9
        assert setup.canvas.paused_ms() == 9 * DEFAULT_DELAY
        assert setup.pen.speed() == DEFAULT_SPEED
        assert setup.screen.delay() == DEFAULT_DELAY

    @pytest.mark.parametrize(
        ("distance", "speed"), [(100, 3), (1000, 3), (100, 10), (50, 1), (250, 6), (-100, 3)]
    )
    def test_the_move_formula(self, distance: int, speed: int) -> None:
        setup = Setup()
        setup.pen.speed(speed)

        frames = setup.frames_of(lambda: setup.pen.forward(distance))

        assert frames == move_frames(distance, speed), f"forward({distance}) at speed {speed}"

    @pytest.mark.parametrize(("angle", "speed"), [(90, 3), (360, 1), (45, 10), (180, 6), (-90, 3)])
    def test_the_turn_formula(self, angle: int, speed: int) -> None:
        setup = Setup()
        setup.pen.speed(speed)

        frames = setup.frames_of(lambda: setup.pen.right(angle))

        assert frames == turn_frames(angle, speed), f"right({angle}) at speed {speed}"

    def test_a_turn_outweighs_a_move_at_the_default_speed(self) -> None:
        setup = Setup()

        turn = setup.frames_of(lambda: setup.pen.right(90))
        move = setup.frames_of(lambda: setup.pen.forward(100))

        assert (turn, move) == (12, 9)

    def test_speed_zero_is_one_frame_per_command(self) -> None:
        setup = Setup()
        setup.pen.speed(0)

        assert setup.frames_of(lambda: setup.pen.forward(1000)) == 1
        assert setup.frames_of(lambda: setup.pen.right(720)) == 1
        assert setup.canvas.paused_ms() == DEFAULT_DELAY

    def test_setting_the_speed_is_itself_a_frame(self) -> None:
        setup = Setup()

        assert setup.frames_of(lambda: setup.pen.speed(0)) == 1
        assert setup.frames_of(lambda: setup.pen.speed("fastest")) == 1

    @pytest.mark.parametrize(
        ("name", "action"),
        [
            ("pencolor", lambda pen: pen.pencolor("red")),
            ("fillcolor", lambda pen: pen.fillcolor("red")),
            ("color", lambda pen: pen.color("red", "blue")),
            ("pensize", lambda pen: pen.pensize(3)),
            ("penup", lambda pen: pen.penup()),
            ("pen", lambda pen: pen.pen(pencolor="red", pensize=3, speed=5)),
            ("resizemode", lambda pen: pen.resizemode("auto")),
            ("showturtle", lambda pen: pen.showturtle()),
            ("hideturtle", lambda pen: pen.hideturtle()),
            ("shapesize", lambda pen: pen.shapesize(2)),
            ("shearfactor", lambda pen: pen.shearfactor(0.5)),
            ("tilt", lambda pen: pen.tilt(10)),
            ("tiltangle", lambda pen: pen.tiltangle(45)),
            ("shapetransform", lambda pen: pen.shapetransform(2, 0, 0, 2)),
            ("shape", lambda pen: pen.shape("turtle")),
            ("begin_fill", lambda pen: pen.begin_fill()),
            ("write", lambda pen: pen.write("hello")),
            ("onclick", lambda pen: pen.onclick(lambda x, y: None)),
            ("onrelease", lambda pen: pen.onrelease(lambda x, y: None)),
            ("clearstamp", lambda pen: pen.clearstamp(pen.stamp())),
            ("clearstamps", lambda pen: pen.clearstamps()),
        ],
    )
    def test_one_frame_commands(self, name: str, action: Callable[[Any], Any]) -> None:
        setup = Setup()

        frames = setup.frames_of(lambda: action(setup.pen))

        assert frames == 1, f"{name} cost {frames} frames"

    @pytest.mark.parametrize(
        ("name", "action"),
        [
            ("stamp", lambda pen: pen.stamp()),
            ("ondrag", lambda pen: pen.ondrag(lambda x, y: None)),
            ("degrees", lambda pen: pen.degrees(400)),
            ("radians", lambda pen: pen.radians()),
            ("pos", lambda pen: pen.pos()),
            ("pen getter", lambda pen: pen.pen()),
            ("distance", lambda pen: pen.distance(3, 4)),
            ("shape getter", lambda pen: pen.shape()),
            ("shapesize getter", lambda pen: pen.shapesize()),
            ("tiltangle getter", lambda pen: pen.tiltangle()),
            ("shapetransform getter", lambda pen: pen.shapetransform()),
            ("pencolor getter", lambda pen: pen.pencolor()),
            ("isdown", lambda pen: pen.isdown()),
            ("resizemode getter", lambda pen: pen.resizemode()),
        ],
    )
    def test_free_commands(self, name: str, action: Callable[[Any], Any]) -> None:
        setup = Setup()

        frames = setup.frames_of(lambda: action(setup.pen))

        assert frames == 0, f"{name} cost {frames} frames"

    def test_angle_units_change_what_a_turn_means(self) -> None:
        setup = Setup(tracer=0)

        setup.pen.degrees(400)
        setup.pen.left(100)
        assert setup.pen.heading() == 100
        assert setup.pen.pos() == (0, 0)
        setup.pen.forward(10)
        assert (round(setup.pen.xcor()), round(setup.pen.ycor())) == (0, 10), "a quarter turn"

        setup.pen.radians()
        assert round(setup.pen.heading(), 6) == round(math.pi / 2, 6)
        setup.pen.left(math.pi / 2)
        setup.pen.forward(10)
        assert (round(setup.pen.xcor()), round(setup.pen.ycor())) == (-10, 10)

    def test_pen_state_costs_a_frame_only_when_it_changes(self) -> None:
        setup = Setup()
        entries = setup.pen.undobufferentries()

        assert setup.frames_of(setup.pen.pendown) == 0
        assert setup.frames_of(setup.pen.penup) == 1
        assert setup.frames_of(setup.pen.penup) == 0
        assert setup.frames_of(setup.pen.pendown) == 1
        assert setup.pen.undobufferentries() == entries + 2

    def test_end_fill_is_a_frame_only_while_filling(self) -> None:
        setup = Setup()

        assert setup.frames_of(setup.pen.end_fill) == 0
        setup.pen.begin_fill()
        assert setup.frames_of(setup.pen.end_fill) == 1

    def test_clear_and_reset_are_two_frames(self) -> None:
        setup = Setup()

        assert setup.frames_of(setup.pen.clear) == 2
        assert setup.frames_of(setup.pen.reset) == 2

    def test_reset_restores_the_default_pen_and_clear_does_not(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.pencolor("red")
        setup.pen.pensize(4)
        setup.pen.speed(9)
        setup.pen.penup()
        setup.pen.forward(30)
        setup.pen.left(45)

        setup.pen.clear()
        assert (setup.pen.pencolor(), setup.pen.pensize(), setup.pen.speed()) == ("red", 4, 9)
        assert setup.pen.isdown() is False
        assert (round(setup.pen.xcor()), setup.pen.heading()) == (30, 45)

        setup.pen.reset()
        assert (setup.pen.pencolor(), setup.pen.pensize(), setup.pen.speed()) == ("black", 1, 3)
        assert setup.pen.isdown() is True
        assert (setup.pen.pos(), setup.pen.heading()) == ((0, 0), 0)

    def test_setheading_turns_the_shorter_way(self) -> None:
        setup = Setup()

        long_way = setup.frames_of(lambda: setup.pen.setheading(270))

        assert setup.pen.heading() == 270
        assert long_way == turn_frames(90, DEFAULT_SPEED) == 12

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_teleport_is_two_pen_changes(self) -> None:
        setup = Setup()

        assert setup.frames_of(lambda: setup.pen.teleport(50, 50)) == 2
        setup.pen.penup()
        assert setup.frames_of(lambda: setup.pen.teleport(0, 0)) == 1

    def test_home_is_a_move_plus_a_turn(self) -> None:
        setup = Setup()
        reference = setup.add_turtle()
        setup.pen.forward(100)
        setup.pen.left(30)
        reference.forward(100)
        reference.left(30)

        home = setup.frames_of(setup.pen.home)
        parts = setup.frames_of(lambda: reference.goto(0, 0)) + setup.frames_of(
            lambda: reference.setheading(0)
        )

        assert home == parts

    def test_a_circle_is_at_least_four_frames_per_step_plus_hops(self) -> None:
        frames = {}
        for radius in (50, 1000):
            setup = Setup()
            setup.pen.begin_poly()
            frames[radius] = setup.frames_of(lambda pen=setup.pen, r=radius: pen.circle(r))
            setup.pen.end_poly()
            steps = len(setup.pen.get_poly()) - 1
            assert steps == (20 if radius == 50 else 60)
            assert frames[radius] >= 4 * steps, f"{frames[radius]} frames for {steps} steps"

        assert frames[50] == 104
        assert frames[1000] > 4 * 60 + 60, "longer edges add hop frames"

    def test_a_circle_at_speed_zero_is_two_frames(self) -> None:
        setup = Setup()
        setup.pen.speed(0)

        assert setup.frames_of(lambda: setup.pen.circle(50)) == 2

    def test_undoing_a_move_costs_the_frames_of_the_move(self) -> None:
        setup = Setup()
        forward = setup.frames_of(lambda: setup.pen.forward(100))

        undo = setup.frames_of(setup.pen.undo)

        assert undo == forward == 9

    def test_dot_is_a_short_move_with_a_few_frames(self) -> None:
        setup = Setup()
        items = len(setup.pen.items)
        entries = setup.pen.undobufferentries()

        frames = setup.frames_of(setup.pen.dot)

        assert 1 <= frames <= 5
        assert 1 <= len(setup.pen.items) - items <= 2
        assert setup.pen.undobufferentries() == entries + 1

    def test_tracer_zero_removes_every_frame(self) -> None:
        setup = Setup(tracer=0)

        setup.pen.forward(1000)
        setup.pen.right(90)
        setup.pen.pencolor("red")
        setup.pen.circle(50)
        setup.pen.dot()

        assert setup.canvas.frames() == 0
        assert setup.canvas.paused_ms() == 0

    def test_update_is_one_frame_without_a_pause(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(100)

        frames = setup.frames_of(setup.screen.update)

        assert frames == 1
        assert setup.canvas.paused_ms() == 0

    def test_setting_a_non_zero_tracer_performs_an_update(self) -> None:
        setup = Setup(tracer=0)

        assert setup.frames_of(lambda: setup.screen.tracer(1)) == 1
        assert setup.frames_of(lambda: setup.screen.tracer(0)) == 0

    def test_tracer_two_draws_every_second_update_without_pause_or_hops(self) -> None:
        setup = Setup(tracer=2)

        setup.pen.forward(1000)
        setup.pen.forward(1000)

        assert setup.canvas.frames() == 1
        assert setup.canvas.paused_ms() == 0

    def test_delay_zero_keeps_the_frames_and_drops_the_pause(self) -> None:
        setup = Setup()
        setup.screen.delay(0)

        setup.pen.forward(100)

        assert setup.canvas.frames() == 9
        assert setup.canvas.paused_ms() == 0

    def test_update_transforms_every_turtle_shape(self) -> None:
        setup = Setup(tracer=0)
        pens = [setup.pen, setup.add_turtle(), setup.add_turtle()]
        for pen in pens:
            pen.shape("turtle")
        setup.canvas.reset_log()

        setup.screen.update()

        assert len(setup.canvas.coords_set) == len(pens)
        assert {size for _, size in setup.canvas.coords_set} == {2 * 24}, "24 vertices"

        setup.screen.register_shape("big", tuple((index, index) for index in range(500)))
        pens[0].shape("big")
        setup.canvas.reset_log()
        setup.screen.update()
        assert sorted(size for _, size in setup.canvas.coords_set) == [48, 48, 1000]

    def test_a_hidden_turtle_s_shape_is_not_redrawn(self) -> None:
        setup = Setup()
        setup.pen.speed(0)
        shape_item = setup.pen.turtle._item  # noqa: SLF001

        setup.pen.forward(10)
        shown = sum(1 for item, _ in setup.canvas.coords_set if item == shape_item)
        setup.pen.hideturtle()
        setup.canvas.reset_log()
        setup.pen.forward(10)
        hidden = sum(1 for item, _ in setup.canvas.coords_set if item == shape_item)

        assert shown >= 1
        assert hidden == 0
        assert setup.canvas.frames() == 1, "the frame itself is still drawn"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_no_animation_updates_once_on_exit(self) -> None:
        setup = Setup()
        screen: Any = setup.screen

        with screen.no_animation():
            setup.pen.forward(1000)
            inside = setup.canvas.frames()
            assert setup.screen.tracer() == 0

        assert inside == 0
        assert setup.canvas.frames() == 1
        assert setup.screen.tracer() == 1

        setup.screen.tracer(0)
        with screen.no_animation():
            setup.pen.forward(1000)
        assert setup.canvas.frames() == 1, "restoring tracer(0) draws nothing"

    def test_write_under_tracer_zero(self) -> None:
        setup = Setup(tracer=0)

        setup.pen.write("hello")

        fixed = sys.version_info >= (3, 11, 1) or (3, 10, 8) <= sys.version_info < (3, 11)
        expected = 0 if fixed else 1
        assert setup.canvas.frames() == expected
        assert setup.canvas.texts == ["hello"]

    def test_write_with_move_moves_to_the_text_s_right_edge(self) -> None:
        setup = Setup(tracer=0)

        setup.pen.write("hello", move=True)

        assert setup.pen.xcor() == 9, "the recording canvas reports a 10-wide box"
        assert setup.pen.ycor() == 0


class TestMovesCopyTheItemList:
    """`forward()` | O(i + f) | O(i): every move copies the turtle's item list
    into its undo entry, buffer or not, and a buffer retains the copies."""

    @staticmethod
    def with_items(count: int, undobuffersize: int = 1000) -> Setup:
        setup = Setup(tracer=0, undobuffersize=undobuffersize)
        setup.pen.penup()
        for _ in range(count):
            setup.pen.write("x")
        setup.pen.forward(1)
        return setup

    def test_the_entry_holds_a_copy_of_the_item_list(self) -> None:
        setup = self.with_items(10)
        pen = setup.pen

        pen.forward(1)

        assert pen.undobuffer is not None
        entry = pen.undobuffer.buffer[pen.undobuffer.ptr]
        assert entry[0] == "go"
        copied = entry[4][3]
        assert copied == pen.items
        assert copied is not pen.items

    def test_allocation_per_move_follows_the_items(self) -> None:
        small = self.with_items(10)
        large = self.with_items(10_000)
        assert (len(small.pen.items), len(large.pen.items)) == (11, 10_001)

        peaks = [peak_bytes(lambda: small.pen.forward(1)), peak_bytes(lambda: large.pen.forward(1))]

        assert peaks[1] > peaks[0] * 50, f"forward() at 11 and 10,001 items allocated {peaks}"

    def test_the_copy_is_made_without_a_buffer_too(self) -> None:
        small = self.with_items(10)
        large = self.with_items(10_000)
        small.pen.setundobuffer(None)
        large.pen.setundobuffer(None)

        peaks = [peak_bytes(lambda: small.pen.forward(1)), peak_bytes(lambda: large.pen.forward(1))]

        assert peaks[1] > peaks[0] * 50, f"forward() without a buffer allocated {peaks}"
        assert large.pen.undobufferentries() == 0

    @pytest.mark.timing
    def test_time_per_move_follows_the_items(self) -> None:
        small = self.with_items(10)
        large = self.with_items(10_000)

        durations = [
            best_ns(lambda: small.pen.forward(1), inner=20),
            best_ns(lambda: large.pen.forward(1), inner=20),
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 10, f"1,000x the items cost x{ratio:.1f}: {durations} ns"

    def test_the_buffer_retains_one_copy_per_move(self) -> None:
        setup = self.with_items(1000)
        pen = setup.pen

        for _ in range(100):
            pen.forward(1)

        assert pen.undobuffer is not None
        copies = [
            entry[4][3]
            for entry in pen.undobuffer.buffer
            if isinstance(entry, tuple) and entry[0] == "go"
        ]
        assert len({id(copy) for copy in copies}) == len(copies) == 101
        assert all(len(copy) >= 1001 for copy in copies)

    def test_one_line_item_per_42_segments(self) -> None:
        setup = Setup(tracer=0)
        pen = setup.pen
        counts = {}

        for moves in range(1, 127):
            pen.forward(1)
            pen.left(3)
            counts[moves] = len(pen.items)

        assert (counts[41], counts[42], counts[84], counts[126]) == (1, 2, 3, 4)

    def test_every_colour_change_starts_a_new_item(self) -> None:
        setup = Setup(tracer=0)
        pen = setup.pen

        for step in range(100):
            pen.pencolor("red" if step % 2 else "blue")
            pen.forward(1)

        assert len(pen.items) == 100, "the first change precedes any drawing"

    def test_a_width_change_splits_a_drawn_line(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(10)
        items = len(setup.pen.items)

        setup.pen.pensize(3)

        assert len(setup.pen.items) == items + 1


class TestUndoAndTheBuffer:
    """`undo()` | O(i²): a move's undo compares the item list with its saved
    copy pairwise; `setundobuffer()` | O(size); `undobufferentries()` | O(u)."""

    @staticmethod
    def with_items(count: int, undobuffersize: int = 1000) -> Setup:
        setup = Setup(tracer=0, undobuffersize=undobuffersize)
        setup.pen.penup()
        for _ in range(count):
            setup.pen.write("x")
        return setup

    @staticmethod
    def comparisons(action: Callable[[], Any]) -> int:
        before = ItemId.comparisons
        action()
        return ItemId.comparisons - before

    def test_undoing_a_move_is_quadratic_in_the_items(self) -> None:
        counts = []
        for items in (200, 2000):
            setup = self.with_items(items)
            setup.pen.forward(1)
            counts.append(self.comparisons(setup.pen.undo))
            assert setup.pen.xcor() == 0

        assert counts[1] > counts[0] * 50, f"10x the items compared {counts} times"

    def test_undoing_a_write_or_dot_removes_its_items(self) -> None:
        setup = Setup(tracer=0)
        before = list(setup.pen.items)

        setup.pen.write("hello")
        text = setup.pen.items[-1]
        assert text in setup.canvas.items
        setup.pen.undo()
        assert text not in setup.canvas.items
        assert setup.pen.items == before

        setup.pen.dot(5)
        assert len(setup.pen.items) > len(before)
        setup.pen.undo()
        assert setup.pen.items == before
        assert setup.pen.undobufferentries() == 0

    def test_undo_restores_position_and_heading(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(10)
        setup.pen.left(90)

        setup.pen.undo()
        assert setup.pen.heading() == 0
        setup.pen.undo()
        assert setup.pen.pos() == (0, 0)
        assert setup.pen.undobufferentries() == 0

    def test_a_new_buffer_is_allocated_up_front(self) -> None:
        setup = Setup(tracer=0)

        peaks = [
            peak_bytes(lambda: setup.pen.setundobuffer(1000)),
            peak_bytes(lambda: setup.pen.setundobuffer(100_000)),
        ]

        assert peaks[1] > peaks[0] * 50, f"buffers of 1,000 and 100,000 allocated {peaks}"
        assert setup.pen.undobufferentries() == 0

    def test_clear_reinstalls_the_construction_size(self) -> None:
        setup = Setup(tracer=0, undobuffersize=100_000)
        setup.pen.setundobuffer(1)
        assert setup.pen.undobuffer.bufsize == 1

        setup.pen.clear()

        assert setup.pen.undobuffer.bufsize == 100_000

    def test_the_ring_keeps_the_last_entries(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.setundobuffer(10)

        for _ in range(20):
            setup.pen.forward(1)

        assert setup.pen.undobufferentries() == 10
        for _ in range(10):
            setup.pen.undo()
        assert setup.pen.xcor() == 10, "the last ten moves were undone, not the first"
        assert setup.pen.undobufferentries() == 0
        setup.pen.undo()
        assert setup.pen.xcor() == 10

    @pytest.mark.timing
    def test_counting_entries_walks_the_whole_buffer(self) -> None:
        small = Setup(tracer=0, undobuffersize=1000)
        large = Setup(tracer=0, undobuffersize=100_000)
        small.pen.forward(1)
        large.pen.forward(1)

        durations = [
            best_ns(small.pen.undobufferentries, inner=10),
            best_ns(large.pen.undobufferentries, inner=10),
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 20, f"100x the slots cost x{ratio:.1f}: {durations} ns"

    def test_removing_the_buffer_breaks_stamps(self) -> None:
        setup = Setup(tracer=0)
        stamp = setup.pen.stamp()
        setup.pen.setundobuffer(None)

        assert setup.pen.undobufferentries() == 0
        setup.pen.forward(1)
        setup.pen.write("x")
        setup.pen.dot()
        setup.pen.undo()
        with pytest.raises(AttributeError):
            setup.pen.stamp()
        with pytest.raises(AttributeError):
            setup.pen.clearstamp(stamp)
        with pytest.raises(AttributeError):
            setup.pen.clearstamps()
        setup.pen.stampItems.clear()
        setup.pen.clearstamps()
        assert setup.pen.stampItems == [], "nothing to clear, nothing dereferenced"


class TestStampsScanTheListAndTheBuffer:
    """`clearstamp()` | O(m + u) and `clearstamps()` | O(n·(m + u)): each
    removal scans the stamp list and the undo buffer, so clearing all of a
    turtle's stamps, directly or through `clear()` and `reset()`, pays a
    buffer scan per stamp."""

    @staticmethod
    def with_stamps(count: int, undobuffersize: int = 1000) -> tuple[Setup, list[Any]]:
        setup = Setup(tracer=0, undobuffersize=undobuffersize)
        ids = [setup.pen.stamp() for _ in range(count)]
        return setup, ids

    @staticmethod
    def comparisons(action: Callable[[], Any]) -> int:
        before = ItemId.comparisons
        action()
        return ItemId.comparisons - before

    def test_stamp_is_one_new_item_and_no_frame(self) -> None:
        setup = Setup()
        items = len(setup.canvas.items)

        stamp = setup.pen.stamp()

        assert len(setup.canvas.items) == items + 1
        assert setup.canvas.frames() == 0
        assert stamp in setup.canvas.items
        assert setup.pen.undobufferentries() == 1

    def test_stamp_transforms_every_vertex_of_the_shape(self) -> None:
        setup = Setup(tracer=0)
        setup.screen.register_shape("big", tuple((index, index) for index in range(500)))
        sizes = {}
        for name in ("turtle", "big"):
            setup.pen.shape(name)
            setup.pen.forward(10)
            setup.canvas.reset_log()
            stamp = setup.pen.stamp()
            sizes[name] = [size for item, size in setup.canvas.coords_set if item == stamp]
            assert setup.canvas.items[stamp][1][:2] != [0.0, 0.0], "placed at the turtle"

        assert sizes == {"turtle": [2 * 24], "big": [2 * 500]}

    def test_clearing_one_stamp_scans_the_stamp_list(self) -> None:
        counts = []
        for stamps in (100, 10_000):
            setup, ids = self.with_stamps(stamps)
            counts.append(
                self.comparisons(lambda pen=setup.pen, last=ids[-1]: pen.clearstamp(last))
            )
            assert setup.pen.undobufferentries() == min(stamps, 1000) - 1

        assert counts[1] > counts[0] * 30, f"100x the stamps compared {counts} times"

    @pytest.mark.timing
    def test_clearing_one_stamp_scans_the_undo_buffer(self) -> None:
        """An unknown id with one stamp keeps the stamp-list scan constant, so only
        the buffer scan varies."""
        durations = []
        for slots in (1000, 100_000):
            setup, _ = self.with_stamps(1, undobuffersize=slots)
            durations.append(best_ns(lambda pen=setup.pen: pen.clearstamp(-1), inner=5))
        ratio = durations[1] / durations[0]

        assert ratio > 10, f"100x the buffer slots cost x{ratio:.1f}: {durations} ns"

    @pytest.mark.parametrize("name", ["clearstamps", "reset"])
    def test_clearing_every_stamp_scans_the_buffer_per_stamp(self, name: str) -> None:
        counts = []
        for stamps in (500, 5000):
            setup, _ = self.with_stamps(stamps)
            counts.append(self.comparisons(getattr(setup.pen, name)))
            assert setup.pen.stampItems == []

        assert counts[1] > counts[0] * 30, f"{name}: 10x the stamps compared {counts} times"

    def test_clearstamps_takes_the_first_or_last_n(self) -> None:
        setup, ids = self.with_stamps(8)

        setup.pen.clearstamps(2)
        assert setup.pen.stampItems == ids[2:]
        setup.pen.clearstamps(-2)
        assert setup.pen.stampItems == ids[2:6]
        setup.pen.clearstamps()
        assert setup.pen.stampItems == []
        assert setup.pen.undobufferentries() == 0


class TestCloneCopiesTheUndoBuffer:
    """`clone()` | O(u + (h + 1)·i + m + p): a deep copy of the turtle, undo
    buffer included, h being the item-list copies the buffer holds."""

    @staticmethod
    def with_history(items: int, moves: int) -> Setup:
        setup = Setup(tracer=0)
        setup.pen.penup()
        for _ in range(items):
            setup.pen.write("x")
        for _ in range(moves):
            setup.pen.forward(1)
        return setup

    def test_allocation_follows_entries_times_items(self) -> None:
        small = self.with_history(10, 10)
        large = self.with_history(1000, 1000)

        peaks = [peak_bytes(small.pen.clone), peak_bytes(large.pen.clone)]

        assert peaks[1] > peaks[0] * 100, f"clone() allocated {peaks}"

    def test_a_circle_entry_holds_one_copy_per_step(self) -> None:
        peaks = []
        for steps in (10, 1000):
            setup = Setup(tracer=0)
            setup.pen.setundobuffer(1)
            setup.pen.circle(50, steps=steps)
            assert setup.pen.undobufferentries() == 1
            peaks.append(peak_bytes(setup.pen.clone))

        assert peaks[1] > peaks[0] * 20, f"clone() with a one-slot buffer allocated {peaks}"

    def test_the_clone_shares_the_screen_and_nothing_else(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(10)

        clone = setup.pen.clone()

        assert clone.getscreen() is setup.screen
        assert setup.screen.turtles() == [setup.pen, clone]
        assert clone.pos() == setup.pen.pos()
        assert clone.items is not setup.pen.items
        assert clone.undobuffer is not setup.pen.undobuffer
        assert clone.undobufferentries() == setup.pen.undobufferentries()


class TestFillingAndPolygons:
    """`end_fill()` | O(p): the p-vertex path goes to Tk in one call;
    `get_poly()` | O(p): a new tuple; `circle()` is `steps` moves."""

    def test_end_fill_passes_the_whole_path_once(self) -> None:
        setup = Setup(tracer=0)
        items = len(setup.pen.items)
        setup.pen.begin_fill()
        assert len(setup.pen.items) == items + 1
        fill_item = setup.pen.items[-1]
        for _ in range(5):
            setup.pen.forward(10)
            setup.pen.left(72)
        setup.canvas.reset_log()

        setup.pen.end_fill()

        assert [size for item, size in setup.canvas.coords_set if item == fill_item] == [2 * 6]
        assert setup.pen.filling() is False

    def test_begin_fill_while_filling_reuses_the_item_and_restarts(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.begin_fill()
        setup.pen.forward(10)
        assert len(setup.pen._fillpath) == 2  # noqa: SLF001
        setup.canvas.reset_log()

        setup.pen.begin_fill()

        assert setup.canvas.created == ["line"], "the line is closed; no second fill polygon"
        assert len(setup.pen._fillpath) == 1  # noqa: SLF001
        assert setup.pen.filling() is True

    def test_get_poly_is_a_fresh_tuple_of_the_moves(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.begin_poly()
        for _ in range(3):
            setup.pen.forward(10)
            setup.pen.left(120)
        setup.pen.end_poly()

        first = setup.pen.get_poly()
        second = setup.pen.get_poly()

        assert first == second
        assert first is not second
        assert len(first) == 4

    @pytest.mark.parametrize(
        ("args", "steps"), [((1000,), 60), ((10,), 13), ((50, None, 6), 6), ((50, 180), 10)]
    )
    def test_circle_steps(self, args: tuple[Any, ...], steps: int) -> None:
        setup = Setup(tracer=0)

        setup.pen.begin_poly()
        setup.pen.circle(*args)
        setup.pen.end_poly()

        assert len(setup.pen.get_poly()) == steps + 1

    def test_a_circle_is_one_undo_entry(self) -> None:
        setup = Setup(tracer=0)

        setup.pen.circle(50, 90)

        assert setup.pen.undobufferentries() == 1
        assert (round(setup.pen.xcor()), round(setup.pen.ycor())) == (50, 50)
        assert round(setup.pen.heading()) == 90
        setup.pen.undo()
        assert setup.pen.undobufferentries() == 0
        assert (round(setup.pen.xcor()), round(setup.pen.ycor())) == (0, 0)
        assert round(setup.pen.heading()) == 0

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_the_context_managers(self) -> None:
        setup = Setup(tracer=0)

        with setup.pen.fill(), setup.pen.poly():
            assert setup.pen.filling() is True
            setup.pen.forward(10)
        assert setup.pen.filling() is False
        assert len(setup.pen.get_poly()) == 2

        with pytest.raises(ValueError), setup.pen.fill():
            assert setup.pen.filling() is True
            raise ValueError
        assert setup.pen.filling() is False

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_teleport_pushes_no_entry_and_restarts_a_fill(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(10)
        entries = setup.pen.undobufferentries()
        items = len(setup.pen.items)

        setup.pen.teleport(50, 50)

        assert setup.pen.pos() == (50, 50)
        assert setup.pen.undobufferentries() == entries + 2, "two pen entries, no move entry"
        buffer = setup.pen.undobuffer.buffer
        newest = buffer[setup.pen.undobuffer.ptr], buffer[setup.pen.undobuffer.ptr - 1]
        assert [entry[0] for entry in newest] == ["pen", "pen"]
        assert len(setup.pen.items) == items + 1, "the drawn line is closed, as by penup()"

        setup.pen.begin_fill()
        items = len(setup.pen.items)
        entries = setup.pen.undobufferentries()
        setup.pen.teleport(0, 0)
        assert len(setup.pen.items) == items + 1, "the fill was closed and a new one begun"
        assert setup.pen.undobufferentries() >= entries + 3, "begin_fill() pushes its own"
        setup.pen.teleport(10, 10, fill_gap=True)
        assert len(setup.pen.items) == items + 1
        assert setup.pen.filling() is True


class TestShapesAndVectors:
    """`Shape()` | O(v); `Shape.addcomponent()` | O(1); `register_shape()`
    is a dict entry; `getshapes()` is sorted; `Vec2D` operations are O(1)."""

    def test_a_polygon_shape_copies_a_list_into_a_tuple(self) -> None:
        points = [(0, 0), (10, 0), (0, 10)]

        shape: Any = turtle.Shape("polygon", points)

        assert shape._data == tuple(points)
        assert isinstance(shape._data, tuple)

    def test_a_compound_shape_appends_components_by_reference(self) -> None:
        shape: Any = turtle.Shape("compound")
        triangle = ((0, 0), (10, 0), (0, 10))

        shape.addcomponent(triangle, "red")
        shape.addcomponent(triangle, "blue", "black")

        assert shape._data == [[triangle, "red", "red"], [triangle, "blue", "black"]]
        assert shape._data[0][0] is triangle
        with pytest.raises(turtle.TurtleGraphicsError):
            turtle.Shape("polygon", triangle).addcomponent(triangle, "red")

    def test_bad_shapes_are_rejected(self) -> None:
        with pytest.raises(turtle.TurtleGraphicsError):
            ShapeClass("blob")
        if sys.version_info >= (3, 14):
            with pytest.raises(AssertionError):
                ShapeClass("image", "picture.gif")
        else:
            assert ShapeClass("image", "picture.gif")._data == "picture.gif"

    def test_register_shape_replaces_and_getshapes_sorts(self) -> None:
        setup = Setup(tracer=0)
        screen = setup.screen
        before = screen.getshapes()

        screen.register_shape("zz", ((0, 0), (10, 0), (0, 10)))
        screen.addshape("aa", ((0, 0), (5, 0), (0, 5)))
        screen.register_shape("zz", ((0, 0), (20, 0), (0, 20)))

        names = screen.getshapes()
        assert names == sorted(names)
        assert names == sorted([*before, "zz", "aa"])
        setup.pen.shape("zz")
        assert setup.pen.get_shapepoly() == ((0, 0), (20, 0), (0, 20))

    def test_a_list_is_registered_as_given_and_unusable(self) -> None:
        setup = Setup(tracer=0)
        polygon: Any = [(0, 0), (5, 0), (0, 5)]

        setup.screen.register_shape("raw", polygon)

        assert "raw" in setup.screen.getshapes()
        with pytest.raises(AttributeError):
            setup.pen.shape("raw")

    def test_an_image_file_is_loaded_by_tk(self) -> None:
        setup = Setup(tracer=0)

        setup.screen.register_shape("picture.gif")

        assert setup.canvas.tk.images_created() == 1
        setup.pen.shape("picture.gif")
        assert setup.pen.get_shapepoly() is None

    def test_switching_shape_type_recreates_the_items(self) -> None:
        setup = Setup(tracer=0)
        compound = turtle.Shape("compound")
        for _ in range(3):
            compound.addcomponent(((0, 0), (10, 0), (0, 10)), "red")
        setup.screen.register_shape("three", compound)
        setup.canvas.reset_log()

        setup.pen.shape("three")

        assert setup.canvas.created == ["polygon"] * 3
        setup.canvas.reset_log()
        setup.pen.shape("turtle")
        assert setup.canvas.created == ["polygon"]
        setup.canvas.reset_log()
        setup.pen.shape("square")
        assert setup.canvas.created == [], "polygon to polygon keeps the item"

    def test_get_shapepoly_transforms_every_vertex(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.shape("square")

        setup.pen.shapetransform(4, -1, 0, 2)

        assert setup.pen.get_shapepoly() == ((50, -20), (30, 20), (-50, 20), (-30, -20))

    def test_vec2d_arithmetic(self) -> None:
        a = turtle.Vec2D(3, 4)
        b = turtle.Vec2D(1, 2)

        assert a + b == (4, 6)
        assert a - b == (2, 2)
        assert a * b == 11
        assert a * 2 == (6, 8)
        assert 2 * a == (6, 8)
        assert -a == (-3, -4)
        assert abs(a) == 5
        rotated = turtle.Vec2D(1, 0).rotate(90)
        assert (round(rotated[0]), round(rotated[1])) == (0, 1)
        assert repr(a) == "(3.00,4.00)"
        assert isinstance(a, tuple)

    def test_pos_and_turtles_return_the_stored_objects(self) -> None:
        setup = Setup(tracer=0)

        assert setup.pen.pos() is setup.pen.pos()
        assert isinstance(setup.pen.pos(), turtle.Vec2D)
        assert setup.screen.turtles() is setup.screen.turtles()
        assert setup.screen.turtles() == [setup.pen]

    def test_pen_getter_builds_an_eleven_key_dict(self) -> None:
        setup = Setup(tracer=0)

        state = setup.pen.pen()

        assert len(state) == 11
        assert state is not setup.pen.pen()
        assert state["pendown"] is True

    def test_distance_and_towards_accept_pairs_vectors_and_turtles(self) -> None:
        setup = Setup(tracer=0)
        other = setup.add_turtle()
        other.penup()
        other.goto(3, 4)

        assert setup.pen.distance(3, 4) == 5
        assert setup.pen.distance((3, 4)) == 5
        assert setup.pen.distance(other.pos()) == 5
        assert setup.pen.distance(other) == 5
        assert round(setup.pen.towards(other)) == 53


class TestScreen:
    """`clear()` | O(I + K²), `mode()` and `setworldcoordinates()` reset from
    another mode and rescale every item in world mode; `bgpic()` caches per
    name; `onkey()` keeps a key list; `Terminator` follows a closed window."""

    def test_the_first_world_coordinates_call_resets_the_screen(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(50)
        line = setup.pen.items[0]
        assert line in setup.canvas.items

        setup.screen.setworldcoordinates(-1, -1, 1, 1)

        assert setup.screen.mode() == "world"
        assert line not in setup.canvas.items
        assert setup.pen.pos() == (0, 0)

    def test_a_later_call_rescales_every_item_once(self) -> None:
        setup = Setup(tracer=0)
        setup.screen.setworldcoordinates(-1, -1, 1, 1)
        setup.pen.forward(0.5)
        setup.pen.write("x")
        line, text = setup.pen.items[0], setup.pen.items[-1]
        setup.screen.update()  # under tracer(0) the line reaches the canvas only now
        before = setup.canvas.coords(line)
        setup.canvas.reset_log()

        setup.screen.setworldcoordinates(-2, -2, 2, 2)

        rescaled = [item for item, _ in setup.canvas.coords_set]
        assert set(rescaled) >= set(setup.canvas.items), "every item was rescaled"
        assert rescaled.count(text) == 1, "once; only the turtle shape is drawn again"
        assert line in setup.canvas.items
        assert before and setup.canvas.coords(line) == [value / 2 for value in before]
        assert round(setup.pen.xcor(), 1) == 0.5

    @pytest.mark.timing
    def test_rescaling_is_quadratic_in_an_item_s_coordinates(self) -> None:
        durations = []
        for points in (200, 2000):
            setup = Setup(tracer=0)
            setup.screen.mode("world")
            setup.canvas.create_polygon(tuple([0.0] * (2 * points)))
            durations.append(
                best_ns(
                    lambda screen=setup.screen: screen.setworldcoordinates(-1, -1, 1, 1), repeats=3
                )
            )
        ratio = durations[1] / durations[0]

        assert ratio > 20, f"10x the coordinates cost x{ratio:.1f}: {durations} ns"

    def test_changing_mode_erases_drawings(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(50)
        line = setup.pen.items[0]

        setup.screen.mode("logo")

        assert setup.screen.mode() == "logo"
        assert line not in setup.canvas.items
        assert setup.pen.pos() == (0, 0)
        assert setup.pen.heading() == 0

    def test_screen_reset_is_every_turtle_s_reset(self) -> None:
        setup = Setup()
        one = setup.frames_of(setup.pen.reset)
        setup.add_turtle()
        setup.add_turtle()

        frames = setup.frames_of(setup.screen.reset)

        assert frames == 3 * one == 6

    def test_clear_empties_everything(self) -> None:
        setup = Setup(tracer=0)
        setup.pen.forward(50)
        setup.screen.onkey(lambda: None, "a")
        TurtleClass._pen = setup.pen
        screen: Any = setup.screen

        setup.screen.clear()

        assert setup.screen.turtles() == []
        assert len(setup.canvas.items) == 1, "only the empty background image item"
        assert setup.screen.tracer() == 1
        assert screen._keys == []
        assert {"<KeyRelease-a>", "<KeyPress-a>"} <= set(setup.canvas.unbound)
        assert TurtleClass._pen is None

    def test_building_a_screen_forgets_the_anonymous_turtle(self) -> None:
        setup = Setup(tracer=0)
        TurtleClass._pen = setup.pen

        TurtleScreenClass(FakeCanvas())

        assert TurtleClass._pen is None

    def test_bgpic_loads_each_name_once(self) -> None:
        setup = Setup(tracer=0)

        setup.screen.bgpic("a.gif")
        setup.screen.bgpic("a.gif")
        assert setup.canvas.tk.images_created() == 1
        setup.screen.bgpic("b.gif")
        assert setup.canvas.tk.images_created() == 2
        setup.screen.bgpic("a.gif")
        assert setup.canvas.tk.images_created() == 2
        assert setup.screen.bgpic() == "a.gif"

    def test_onkey_keeps_one_entry_per_key(self) -> None:
        setup = Setup(tracer=0)
        screen: Any = setup.screen

        setup.screen.onkey(lambda: None, "a")
        setup.screen.onkey(lambda: None, "b")
        setup.screen.onkey(lambda: None, "a")
        assert screen._keys == ["a", "b"]
        screen.onkey(None, "a")
        assert screen._keys == ["b"]
        setup.screen.onkeypress(lambda: None, "c")
        setup.screen.onkeypress(lambda: None, "c")
        assert screen._keys == ["b", "c"]
        setup.screen.onkeypress(lambda: None)
        assert screen._keys == ["b", "c"], "a keyless binding is not listed"
        screen.onkeypress(None)
        assert screen._keys == ["b", "c"], "a keyless unbinding scans the list and removes nothing"

    def test_getters_are_free(self) -> None:
        setup = Setup(tracer=0)

        assert setup.screen.getcanvas() is setup.canvas
        assert setup.screen.window_width() == 400
        assert setup.screen.window_height() == 300
        assert setup.screen.colormode() == 1.0
        setup.screen.colormode(255)
        assert setup.screen.colormode() == 255
        assert setup.screen.bgcolor() == "white"
        assert setup.screen.screensize() == (400, 300)
        assert setup.canvas.frames() == 0

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_save_writes_the_canvas_postscript(self, tmp_path: pathlib.Path) -> None:
        setup = Setup(tracer=0)
        screen: Any = setup.screen
        target = tmp_path / "drawing.eps"

        screen.save(target)

        assert target.read_text().startswith("%!PS")
        with pytest.raises(FileExistsError):
            screen.save(target)
        screen.save(target, overwrite=True)
        with pytest.raises(ValueError, match="extension"):
            screen.save(tmp_path / "drawing.png")

    def test_terminator_follows_a_closed_window(self) -> None:
        setup = Setup()
        TurtleScreenClass._RUNNING = False

        with pytest.raises(turtle.Terminator):
            setup.pen.forward(1)

        assert TurtleScreenClass._RUNNING is True
        setup.pen.forward(1)

    def test_a_bad_colour_is_rejected(self) -> None:
        setup = Setup(tracer=0)

        with pytest.raises(turtle.TurtleGraphicsError):
            setup.pen.pencolor("no such colour")
        screen: Any = setup.screen
        with pytest.raises(turtle.TurtleGraphicsError):
            screen.mode("sideways")


class TestModuleLevelFunctions:
    """Module-level functions delegate to the anonymous turtle and the
    singleton screen, creating the turtle on the first call."""

    @pytest.fixture(autouse=True)
    def _headless(self) -> Iterator[HeadlessScreen]:
        yield install_headless_screen()

    def test_the_first_call_creates_the_anonymous_turtle(self) -> None:
        assert TurtleClass._pen is None

        turtle.forward(50)
        turtle.left(90)

        pen = turtle.getturtle()
        assert pen is turtle.getpen() is TurtleClass._pen
        assert turtle.pos() == (50, 0)
        assert turtle.heading() == 90
        assert turtle.Screen() is TurtleClass._screen
        assert turtle.turtles() == [pen]

    def test_turtle_joins_the_singleton_screen(self) -> None:
        first = turtle.Turtle()
        second = turtle.Pen()

        assert first.getscreen() is second.getscreen() is turtle.Screen()
        assert turtle.turtles() == [first, second]

    def test_aliases(self) -> None:
        assert turtle.RawPen is turtle.RawTurtle
        assert turtle.Pen is turtle.Turtle
        assert turtle.done is turtle.mainloop
        assert turtle.Turtle.fd is turtle.Turtle.forward
        assert turtle.TurtleScreen.addshape is turtle.TurtleScreen.register_shape

    def test_a_raw_turtle_on_a_bare_canvas_finds_its_screen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(turtle, "Canvas", FakeCanvas)
        canvas = FakeCanvas()

        first: turtle.RawTurtle = RawTurtleClass(canvas)
        second: turtle.RawTurtle = RawTurtleClass(canvas)

        assert first.getscreen() is second.getscreen()
        assert first.getscreen().getcanvas() is canvas
        with pytest.raises(turtle.TurtleGraphicsError):
            RawTurtleClass("not a canvas")

    def test_construction_allocates_the_undo_buffer_and_draws_one_frame(self) -> None:
        screen = turtle.Screen()
        canvas: Any = screen.getcanvas()
        canvas.reset_log()
        turtle.RawTurtle(screen)
        assert canvas.frames() == 1

        peaks = [
            peak_bytes(lambda: turtle.RawTurtle(screen, undobuffersize=1000)),
            peak_bytes(lambda: turtle.RawTurtle(screen, undobuffersize=100_000)),
        ]

        assert peaks[1] > peaks[0] * 20, f"turtles with 1,000 and 100,000 slots allocated {peaks}"

    def test_write_docstringdict_writes_one_entry_per_function(
        self, tmp_path: pathlib.Path
    ) -> None:
        stem = tmp_path / "docstrings"

        turtle.write_docstringdict(str(stem))

        docsdict = runpy.run_path(str(stem) + ".py")["docsdict"]
        assert "Turtle.forward" in docsdict
        assert "_Screen.tracer" in docsdict
        assert "Turtle.fd" not in docsdict, "aliases are left out"
        assert len(docsdict) > 90


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


RUNNER = (
    "import sys; sys.path.insert(0, {tests!r}); "
    "from test_turtle_complexity import install_headless_screen; install_headless_screen(); "
    "import runpy; runpy.run_path('block.py', run_name='__main__')"
)


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-c", RUNNER.format(tests=str(pathlib.Path(__file__).parent))],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess with the singleton screen on a
    recording canvas, so `Screen()` and `Turtle()` need no display and
    `mainloop()` returns, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "undobufferentries() == 8" in s)
        mutated = source.replace("undobufferentries() == 8", "undobufferentries() == 9", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
