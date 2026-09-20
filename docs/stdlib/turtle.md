# turtle Module Complexity

The `turtle` module drives a Tk canvas from a small set of commands: move, turn, change the pen,
stamp, write, fill. Every command is both a method of `Turtle` and a module-level function that
acts on an anonymous turtle, and every screen command is both a method of `TurtleScreen` and a
module-level function acting on the singleton `Screen()`. The unit of work is a *frame*: one
canvas redraw plus a pause. A command's Python-side cost is usually small; its frames are what a
program waits for.

`d` is the distance of a move in screen pixels, `a` the angle of a turn in degrees, and `s` the
speed setting, 1 to 10 (0 means fastest). `i` is the canvas items a turtle has drawn: one line
item per 42 segments, plus one for every pen colour or width change, dot, `write()` and fill. `I`
is the items on the whole canvas, `T` the turtles on the screen, `S` the screens created so far,
`u` the undo buffer size (1,000 by default), `h` the item-list copies the buffer holds (one per
buffered move, one per step of a buffered `circle()`), `m` the stamps a turtle has, `p` the vertices of a
fill or recorded polygon, `v` the vertices of a shape, `c` the components of a compound shape, `k`
the registered shapes and `K` the keys bound. `f` is the frames a call triggers. Under `tracer(0)`
it is 0. Under the default `tracer(1)`, a pen change is one frame, a move of `d` at speed `s` is
`1 + ⌊|d| / (3s·1.1^s)⌋` frames and a turn of `a` is `2 + ⌊|a| / 3s⌋`, while speed 0 makes any
move or turn one frame. A frame transforms the `v` vertices of the turtle's shape unless it is hidden,
asks Tk to redraw the canvas, whose cost grows with the items on it, and then pauses for
`delay()` milliseconds, 10 by default. Under `tracer(n)` for `n ≥ 2` only every nth update is
drawn, redrawing all `T` turtles, with no pause and no hop animation.

## Complexity Reference

### Creating Turtles and Screens

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `turtle.RawTurtle(canvas, shape='classic', undobuffersize=1000, visible=True)`, `turtle.RawPen` | O(u + c + S + f) | O(u + c) | Allocates the undo ring buffer up front and one canvas item per shape component; the screen, or a bare Tk canvas's screen, is looked up among the S screens created so far, and a bare canvas with no screen yet gets one built at the `TurtleScreen` cost |
| `turtle.Turtle(shape='classic', undobuffersize=1000, visible=True)`, `turtle.Pen` | O(u + c + S + f) | O(u + c) | A `RawTurtle` on the singleton screen, which the first `Turtle()` creates |
| `turtle.Screen()` | O(1) after the first call | O(1) | The first call builds the Tk window and canvas; later calls return the same object |
| `turtle.TurtleScreen(cv, mode='standard', colormode=1.0, delay=10)` | O(I) | O(1) | Builds the seven built-in shapes and clears the canvas of whatever it holds, which also forgets the anonymous turtle |
| `turtle.ScrolledCanvas(master, width=500, height=350, canvwidth=600, canvheight=500)` | O(1) | O(1) | A Tk frame holding a canvas and two scrollbars; forwards canvas methods to the canvas |
| Module-level functions such as `turtle.forward(distance)` | As the method | As the method | Each call checks for the anonymous turtle, creating it and the screen on the first call, then delegates; `turtle.getturtle()` and `turtle.getpen()` return it |

### Moving and Turning

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `forward(distance)`, `fd(distance)`, `back(distance)`, `bk(distance)`, `backward(distance)` | O(i + f) | O(i) | Copies the turtle's item list into an undo entry before every move, buffer or not; with a buffer the last u entries keep theirs, a `circle()` entry one per step |
| `goto(x, y=None)`, `setpos(x, y=None)`, `setposition(x, y=None)`, `setx(x)`, `sety(y)` | O(i + f) | O(i) | The same move as `forward()`, to an absolute point |
| `home()` | O(i + f) | O(i) | A `goto(0, 0)` and then a `setheading(0)`: the frames of a move plus those of a turn |
| `teleport(x=None, y=None, *, fill_gap=False)` | O(p + f) | O(p) | Python 3.12+. No line, no item-list copy, no hop animation: two pen changes, so two frames and two undo entries with the pen down; a fill in progress is closed and restarted, an `end_fill()` and a `begin_fill()` more, unless `fill_gap=True` |
| `right(angle)`, `rt(angle)`, `left(angle)`, `lt(angle)` | O(1 + f) | O(1) | A 90° turn at the default speed 3 is 12 frames, more than `forward(100)` |
| `setheading(to_angle)`, `seth(to_angle)` | O(1 + f) | O(1) | Turns the shorter way round, so at most half a circle |
| `circle(radius, extent=None, steps=None)` | O(steps·i + f) | O(steps·i) | `steps` defaults to at most 60 for a full circle, fewer for a small radius; each step is a move, a turn and two speed changes, so at speed 1 to 10 at least four frames plus the move's hops, at speed 0 two frames for the whole circle; every step goes into one undo entry |
| `speed(speed=None)` | O(1 + f) | O(1) | Setting it is a pen change, so a frame; 0 removes the hop animation but not the frame per call |
| `pos()`, `position()`, `xcor()`, `ycor()`, `heading()`, `distance(x, y=None)`, `towards(x, y=None)` | O(1) | O(1) | `pos()` returns the stored `Vec2D` itself; `distance()` and `towards()` take a pair, a `Vec2D` or another turtle |
| `degrees(fullcircle=360.0)`, `radians()` | O(1) | O(1) | Change the angle unit without a frame |

### Pen State

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pendown()`, `pd()`, `down()`, `penup()`, `pu()`, `up()` | O(1 + f) | O(1) | A frame and an undo entry when the state changes, nothing otherwise; the change closes the current line, which becomes a new canvas item once it has two points |
| `pensize(width=None)`, `width(width=None)` | O(1 + f) | O(1) | A new width starts a new canvas item; the getter is free |
| `pencolor(*args)`, `fillcolor(*args)`, `color(*args)` | O(1 + f) | O(1) | A new pen colour starts a new canvas item; a setter is one frame, a getter none |
| `pen(pen=None, **pendict)` | O(1 + f) | O(1) | The getter builds an eleven-key dict; the setter applies any number of attributes for one frame |
| `isdown()`, `isvisible()`, `resizemode(rmode=None)` | O(1 + f) | O(1) | Getters are free; setting `resizemode` is a pen change |
| `showturtle()`, `st()`, `hideturtle()`, `ht()` | O(1 + f) | O(1) | A hidden turtle's shape is not transformed and redrawn each frame, which saves O(v) per frame, not the frame |

### Filling, Dots, Text and Polygons

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `begin_fill()` | O(1 + f) | O(p) | Adds the fill's canvas item, or reuses it when already filling, and closes the current line; the path restarts here and every move until `end_fill()` appends one vertex |
| `end_fill()` | O(p + f) | O(p) | Flattens the p-vertex path and hands it to Tk in one call; nothing when not filling |
| `fill()` | O(p + f) | O(p) | Python 3.14+. `begin_fill()` on entry, `end_fill()` on exit, exceptions included |
| `filling()` | O(1) | O(1) | |
| `dot(size=None, *color)` | O(i + f) | O(i) | A zero-length move with the pen down and widened: the cost of a move, up to two new items, and a few frames |
| `write(arg, move=False, align='left', font=('Arial', 8, 'normal'))` | O(n + f) | O(n) | n = characters of `str(arg)`, built here and laid out by Tk; one item, one frame; `move=True` adds a move to the text's right edge, at a move's O(i) cost |
| `begin_poly()`, `end_poly()`, `poly()` | O(1) | O(p) | Every move while recording appends one vertex; `poly()` is Python 3.14+ |
| `get_poly()` | O(p) | O(p) | A new tuple of the recorded vertices |

### Stamps

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stamp()` | O(v) | O(v) | Transforms the shape's vertices into one new canvas item (c items for a compound shape); no frame, so it appears with the next one; requires an undo buffer |
| `clearstamp(stampid)` | O(m + u) | O(1) | Scans the stamp list and the whole undo buffer; one frame |
| `clearstamps(n=None)` | O(n·(m + u)) | O(n) | One `clearstamp()` per stamp, so clearing all m stamps is O(m·(m + u)); one frame |

### Shapes and Appearance

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shape(name=None)` | O(c + f) | O(c) | Switching to a shape of another type replaces the turtle's canvas items, one per component; the getter is free |
| `shapesize(stretch_wid=None, stretch_len=None, outline=None)`, `turtlesize(...)`, `shearfactor(shear=None)`, `tilt(angle)`, `tiltangle(angle=None)`, `shapetransform(t11=None, t12=None, t21=None, t22=None)` | O(1 + f) | O(1) | Setters recompute the 2×2 shape transform and cost one frame; getters are free |
| `get_shapepoly()` | O(v) | O(v) | Transforms every vertex of a polygon shape; `None` for an image shape |
| `Shape(type_, data=None)` | O(v) | O(v) | A `'polygon'` keeps a tuple, copying a list; a `'compound'` starts empty; an `'image'` takes a Tk `PhotoImage`, which Python 3.14+ asserts and earlier versions load only for an existing `.gif` path, so register image files by name instead |
| `Shape.addcomponent(poly, fill, outline=None)` | O(1) | O(1) | Appends the polygon by reference; raises `TurtleGraphicsError` on a non-compound shape |
| `register_shape(name, shape=None)`, `addshape(name, shape=None)` | O(v) | O(v) | One dict entry, replacing any shape of that name; a tuple of pairs becomes a polygon `Shape`, a file name makes Tk load the image, and a list is stored as given, which `shape()` cannot use, so pass a tuple or a `Shape` |
| `getshapes()` | O(k log k) | O(k) | Sorted names |

### Undo, Clearing and Cloning

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `undo()` | O(steps·i² + f) | O(steps) | Undoing a move compares the current item list with the saved copy pairwise, then moves back at the same speed; a turn or pen change is O(1); a stamp is a `clearstamp()`, O(m + u); a `circle()`, `dot()` or `write()` entry is a sequence of steps, each undone in turn, and steps is 1 for a plain move |
| `setundobuffer(size)` | O(size) | O(size) | Replaces the buffer, freeing the old history; `None` or 0 removes it, after which `stamp()` and `clearstamp()` raise `AttributeError`, as does `clearstamps()` with a stamp to clear |
| `undobufferentries()` | O(u) | O(1) | Counts the empty slots of the whole buffer |
| `clear()` | O(i + u + m·(m + u) + f) | O(m + u) | Deletes every item, clears every stamp through `clearstamp()` from a copy of the stamp list, and installs a fresh undo buffer of the size the turtle was built with; the turtle stays put |
| `reset()` | O(i + u + m·(m + u) + f) | O(m + u) | `clear()` plus home position, heading and default pen |
| `clone()` | O(u + (h + 1)·i + m + p + f) | O(u + (h + 1)·i + m + p) | Deep-copies the turtle: its item list, its stamps, its polygon, the undo buffer's u slots and each of the h item-list copies they hold |

### Turtle Events and Accessors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `onclick(fun, btn=1, add=None)`, `onrelease(fun, btn=1, add=None)`, `ondrag(fun, btn=1, add=None)` | O(1 + f) | O(1) | One binding on the turtle's canvas item; `onclick()` and `onrelease()` cost a frame, `ondrag()` none |
| `getscreen()`, `getturtle()`, `getpen()` | O(1) | O(1) | The screen the turtle draws on, and the turtle itself |

### TurtleScreen

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `clear()`, `clearscreen()` | O(I + K²) | O(K) | Deletes every canvas item in one Tk call, forgets every turtle, unbinds every key with a scan of the key list per key, and turns tracing back on |
| `reset()`, `resetscreen()` | O(T·(i + u + m·(m + u)) + T·f) | O(T·(m + u)) | Each turtle's `reset()`, frames included |
| `mode(mode=None)` | O(1) to read | O(1) | Setting a mode is a screen `reset()`, at that cost, which erases every drawing |
| `setworldcoordinates(llx, lly, urx, ury)` | O(I + Σc²) | O(c) | In world mode already, rescales every item, quadratic in the coordinates c of each item, so a big filled polygon dominates; from another mode, resets the screen instead; one frame |
| `tracer(n=None, delay=None)` | O(T·v + f) | O(1) | Setting a non-zero n performs an `update()`; 0 turns frames off until `update()`; n ≥ 2 draws every nth update with no pause and no hop animation |
| `update()` | O(T·v) | O(1) | Redraws every turtle's shape and the canvas once, without the pause |
| `no_animation()` | O(T·v) | O(1) | Python 3.14+. `tracer(0)` on entry and the previous tracer on exit, whose one frame is the update a non-zero tracer performs |
| `delay(delay=None)`, `colormode(cmode=None)`, `bgcolor(*args)`, `screensize(canvwidth=None, canvheight=None, bg=None)` | O(1) | O(1) | One attribute or one Tk call each |
| `bgpic(picname=None)` | O(1) after the first load | O(1) per name | Each file name is loaded by Tk once and cached for the screen's life |
| `turtles()`, `getcanvas()`, `window_width()`, `window_height()` | O(1) | O(1) | `turtles()` returns the screen's own list, not a copy |
| `onclick(fun, btn=1, add=None)`, `onscreenclick(...)`, `ontimer(fun, t=0)`, `listen()` | O(1) | O(1) | One Tk binding or timer each |
| `onkey(fun, key)`, `onkeyrelease(fun, key)`, `onkeypress(fun, key=None)` | O(K) | O(1) | Keeps a list of bound keys and scans it; binding `onkeypress()` without a key skips the list, unbinding with `None` does not |
| `save(filename, *, overwrite=False)` | O(I) | O(I) | Python 3.14+. Tk renders the whole canvas to PostScript, held as one string before writing |
| `mainloop()`, `done()`, `textinput(title, prompt)`, `numinput(title, prompt, default=None, minval=None, maxval=None)` | Blocks | O(1) | The Tk event loop until the window closes, or a dialog until it is dismissed |

### Screen

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `setup(width=0.5, height=0.75, startx=None, starty=None)` | O(T·v) | O(1) | Window geometry, then one `update()` |
| `title(titlestring)` | O(1) | O(1) | Window title |
| `bye()`, `exitonclick()` | O(1) | O(1) | `exitonclick()` binds `bye()` to a click and enters the event loop; after `bye()` the next update raises `Terminator` |

### Vectors, Exceptions and Utilities

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `turtle.Vec2D(x, y)` | O(1) | O(1) | A tuple subclass: `+`, `-` and `rotate(angle)` build a new vector, `abs()` is the length, and `*` is the dot product with a vector and scaling with a number |
| `turtle.TurtleGraphicsError` | O(1) | O(1) | A bad shape type, mode, colour, stretch factor or transform |
| `turtle.Terminator` | O(1) | O(1) | Raised by the next screen update after the window was closed |
| `turtle.write_docstringdict(filename='turtle_docstringdict')` | O(F) | O(F) | Writes every function's docstring to a module file; F functions |

## Frames

### Where the Time Goes

Every move, turn and pen change ends with a frame, and a frame is a canvas redraw followed by a
pause of `delay()` milliseconds. `tracer(0)` suspends frames, and `update()` draws once; the
item-list copy per move is the same either way, while the hop animation and its intermediate
positions are skipped.

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)  # O(1) - no frames from here until update()
pen = Turtle()

for _ in range(4):
    pen.forward(100)  # O(i) - no frame; copies the item list into an undo entry
    pen.right(90)     # O(1) - no frame

screen.update()  # O(T·v) - the one frame this block draws

assert screen.tracer() == 0
assert (round(pen.xcor()), round(pen.ycor())) == (0, 0)
assert round(pen.heading()) == 0
assert pen.undobufferentries() == 8  # four moves and four turns
```

### Speed, Delay and the Tracer

Speed only changes how many frames a move or turn is cut into. At speed 0 a command is still one
frame, and every frame still pauses; `delay(0)` removes the pause, and `tracer(0)` removes the
frame. On Python 3.14+ `no_animation()` is `tracer(0)` for a block, and restoring a non-zero
tracer on exit is the one update that shows the result.

```python
from turtle import Screen, Turtle

screen = Screen()
pen = Turtle()

pen.speed(0)      # O(1 + f) - itself a pen change, so one frame
assert pen.speed() == 0
assert screen.delay() == 10  # milliseconds paused after every frame

screen.delay(0)   # O(1) - frames no longer pause
screen.tracer(0)  # frames stop altogether until update()
pen.circle(50)    # O(steps·i) - no frame at all now
assert screen.tracer() == 0
```

## The Undo Buffer

A turtle keeps its last `u` actions, 1,000 by default. Every move copies the turtle's whole item
list into its entry, so a turtle that has drawn many separate items pays O(i) per move and holds
a copy for every buffered move. Removing the buffer with `setundobuffer(None)` stops the retention, not
the copy, and stamps need a buffer.

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)
pen = Turtle()

for _ in range(3):
    pen.forward(10)  # O(i) - one undo entry per move
assert pen.undobufferentries() == 3  # O(u) - counts the whole buffer

pen.undo()  # O(i²) - compares the item list with the saved copy pairwise
assert pen.undobufferentries() == 2
assert round(pen.xcor()) == 20

pen.setundobuffer(10)  # O(size) - a fresh, empty buffer
assert pen.undobufferentries() == 0
for _ in range(20):
    pen.forward(1)
assert pen.undobufferentries() == 10  # the ring keeps only the last ten

pen.setundobuffer(None)  # frees the history; moves still copy the item list, then drop it
try:
    pen.stamp()
except AttributeError:
    pass
else:
    raise AssertionError("stamp() worked without an undo buffer")
```

## Stamps

`stamp()` is cheap, but each `clearstamp()` scans both the stamp list and the undo buffer, and
`clearstamps()` is one such scan per stamp. Clearing every stamp of a turtle is quadratic, and
so is `clear()` or `reset()` on a turtle carrying many stamps.

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)
pen = Turtle()

ids = [pen.stamp() for _ in range(8)]  # O(v) each - no frame until the next update
assert len(ids) == 8
assert pen.undobufferentries() == 8

pen.clearstamp(ids[0])  # O(m + u) - scans the stamps and the undo buffer
assert pen.undobufferentries() == 7  # the stamp's entry is removed too

pen.clearstamps(2)   # O(n·(m + u)) - the first two remaining
pen.clearstamps(-2)  # the last two
pen.clearstamps()    # O(m·(m + u)) - everything left
assert pen.undobufferentries() == 0
```

## Filling and Polygons

`begin_fill()` opens a path that every move extends by one vertex, and `end_fill()` hands the
whole path to Tk at once. `begin_poly()` records the same vertices for `get_poly()`, which is
how a drawn outline becomes a registered shape.

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)
pen = Turtle()

pen.begin_poly()   # O(1) - vertices are recorded from here
pen.begin_fill()   # O(1) - one canvas item for the fill
for _ in range(3):
    pen.forward(60)   # O(i) - appends a vertex to the fill path and the polygon
    pen.left(120)
assert pen.filling() is True
pen.end_fill()     # O(p) - the p-vertex path goes to Tk in one call
pen.end_poly()
assert pen.filling() is False

triangle = pen.get_poly()  # O(p) - a new tuple
assert len(triangle) == 4  # start point plus three moves

screen.register_shape("tri", triangle)  # O(v) - one dict entry
assert "tri" in screen.getshapes()      # O(k log k)
pen.shape("tri")  # O(c + f)
assert pen.shape() == "tri"
assert len(pen.get_shapepoly()) == 4  # O(v) - transformed copy
```

### Circles Are Polygons

`circle()` is a polygon of `steps` moves, each with the cost of a move. With `steps` omitted it
uses at most 60 for a full circle, so a circle is at most 60 moves however large the radius; passing
`steps` sets it directly, which is also how regular polygons are drawn.

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)
pen = Turtle()

pen.begin_poly()
pen.circle(1000)  # O(steps·i) - steps capped at 60 for a full circle
pen.end_poly()
assert len(pen.get_poly()) == 61  # the start point plus 60 moves

pen.begin_poly()
pen.circle(50, steps=6)  # a hexagon: six moves
pen.end_poly()
assert len(pen.get_poly()) == 7

pen.begin_poly()
pen.circle(50, 180)  # a semicircle: about half the steps of the full circle
pen.end_poly()
assert len(pen.get_poly()) == 11
```

## World Coordinates

The first `setworldcoordinates()` switches the screen to world mode, and switching mode is a
screen `reset()` that erases every drawing. A later call rescales every canvas item in place,
walking each item's coordinate list from the front repeatedly, so it is quadratic in the
vertices of a filled polygon.

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)
pen = Turtle()
pen.forward(50)

screen.setworldcoordinates(-1, -1, 1, 1)  # O(T·(i + u + m·(m + u))) - a reset: the line is gone
assert screen.mode() == "world"
assert pen.pos() == (0, 0)

pen.forward(0.5)
screen.setworldcoordinates(-2, -2, 2, 2)  # O(I + Σc²) - rescales the line, keeps it
assert round(pen.xcor(), 1) == 0.5
```

## Common Patterns

### Draw Fast, Then Show

```python
from turtle import Screen, Turtle

screen = Screen()
screen.tracer(0)      # no frames while drawing
pen = Turtle()
pen.hideturtle()      # O(1 + f) - no shape to transform per frame either
pen.setundobuffer(None)  # moves no longer retain item-list copies

for step in range(1, 61):
    pen.forward(step * 2)  # O(i) - one item per 42 segments at one colour
    pen.left(59)

screen.update()  # O(T·v) - the single frame
assert pen.isvisible() is False
assert pen.undobufferentries() == 0
screen.mainloop()  # blocks until the window is closed
```

## Performance Best Practices

✅ **Do**:

- Draw under `tracer(0)` and call `update()` once, or use `no_animation()`: the item-list copies are the same, the frames and hop animation are gone
- Set `delay(0)` when animation should stay visible but not pause after every frame
- Keep one pen colour and width across a long path: an item per 42 segments, not per segment, keeps `i` small
- Call `setundobuffer(None)` on a turtle that draws thousands of items and never undoes: it stops retaining O(h·i) copies
- Change several pen attributes in one `pen(...)` call: one frame instead of one per attribute
- Pass `steps` to `circle()` when a coarser polygon will do: each step is a move

❌ **Avoid**:

- Turning at low speed: a 90° turn at speed 3 is 12 frames, and `home()` turns as well as moves
- `clearstamps()` or `clear()` on a turtle with thousands of stamps: one undo-buffer scan per stamp
- `undo()` as a drawing primitive on a turtle with many items: each undone move is O(i²)
- `clone()` of a turtle with a full undo buffer and many items: it deep-copies O(h·i) references
- A `setworldcoordinates()` call after drawing, expecting the drawing to survive: the first one resets the screen
- `speed(0)` as the fix for a slow program: every command is still a frame with a pause

## Version Notes

- **Python 3.10.8+ and 3.11.1+**: `write()` goes through the tracer, so under `tracer(0)` it draws no frame
- **Python 3.12+**: Added `teleport()`
- **Python 3.13+**: Removed `settiltangle()`; `tiltangle(angle)` sets the tilt
- **Python 3.14+**: Added the `fill()`, `poly()` and `no_animation()` context managers and `save()`; `register_shape()` accepts PNG, PGM and PPM files as well as GIF, and `Shape('image', data)` requires a `PhotoImage`
- **All Python 3**: `stamp()` and `clearstamp()` raise `AttributeError` on a turtle whose undo buffer was removed with `setundobuffer(None)`, and so does `clearstamps()` with a stamp to clear

## Related Modules

- **[tkinter](tkinter.md)** - The canvas every frame redraws; `getcanvas()` exposes it
- **[math](math.md)** - The trigonometry behind `Vec2D.rotate()`, `distance()` and `towards()`
