# turtledemo Module Complexity

The `turtledemo` package holds nineteen example programs for the [turtle](turtle.md) module and a
Tk viewer that lists, shows and runs them. Each demo is a module with a `main()` function, and
nothing in a demo runs until `main()` is called. A `main()` takes no input: it draws a picture
whose sizes are written into its own source, or sets up an event-driven one, so apart from
`round_dance`'s its cost is a constant. What makes the demos worth pricing is the recursive and generative helpers they are
built from, whose size arguments the demos hard-code.

Bounds count turtle commands - moves, turns, clones, stamps - and the Python work around them. What one command
costs, its animation frames, a clone's copy of the undo buffer, is priced on the
[turtle](turtle.md) page, whose `I` (items on the canvas) and `K` (keys bound) are used here
unchanged. `e` is the files in the package directory, `c` the characters of a demo's source, and
`L` the level or depth argument of a recursive helper. Variables used by one row are defined in
its Notes.

## Complexity Reference

### Package and viewer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import turtledemo` | O(1) | O(1) | The package body is a docstring |
| `import turtledemo.<demo>` | O(1) | O(1) | Defines the demo's functions; draws nothing and opens no window. Loading `turtle` and `tkinter` is not priced |
| `python -m turtledemo`, `turtledemo.__main__.main()` | O(e) | O(e) | To open: builds a `DemoWindow`, then runs the Tk event loop until it is closed, each START costing its demo; needs a display |
| `turtledemo.__main__.getExampleEntries()` | O(e) | O(e) | Lists the directory on every call: each `.py` file whose name does not start with `_`, in directory order |
| `DemoWindow.loadfile(filename)` | O(I + K² + c) | O(K + c) | Clears the screen, imports the demo on its first load only, then reads its whole source into the text pane |
| `DemoWindow.startDemo()`, the START button | O(I + K²) + `main()` | O(K) + `main()` | Clears the screen, then runs `main()` to completion; an event-driven demo returns `"EVENTLOOP"` at once and goes on in its callbacks |
| `DemoWindow.stopIt()`, the STOP button | O(I + K²) | O(K) | O(1) while `main()` runs; after an event-driven demo's `main()` has returned, it clears the screen. A running `main()` raises `turtle.Terminator` at its next screen update, which every drawing command makes under `tracer(1)`. The click is seen only while a frame redraws the canvas, and under `tracer(0)` only `update()` redraws or checks, so the demo runs on to the `update()` after the one that saw it |
| `python -m turtledemo.<demo>` | O(1) + `main()` | O(1) + `main()` | To start: runs `main()`, then the Tk event loop until the window is closed, where an event-driven demo's callbacks go on drawing |

### Recursive and generative helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fractalcurves.CurvesTurtle.hilbert(size, level, parity)` | O(4^L) | O(L) | 4^L − 1 moves; the space is the recursion |
| `CurvesTurtle.fractal(dist, depth, dir)` | O(4^L) | O(L) | One Koch edge: 4^L moves |
| `CurvesTurtle.fractalgon(n, rad, lev, dir)` | O(v·4^L) | O(L) | v = n, the sides; one `fractal()` per side |
| `tree.tree(plist, l, a, f)` | O(q·2^L) | O(q·2^L) | q = pens in `plist`; L = levels until the branch length is 3 or less. Every pen moves once and is cloned once per level, and the clones stay on the screen. A generator that never yields: all the drawing happens in the first `next()` |
| `forest.tree(tlist, size, level, widthfactor, branchlists, ...)` | O(L·b^L) | O(b^L) | For one starting turtle; b = branches per fork, 2 or more. Lazy: each `next()` draws at most one branch and makes at most b clones, and every turtle stays on the screen. A branch L levels down passes its yield up through L nested generators |
| `minimal_hanoi.hanoi(n, from_, with_, to_)` | O(2^d) | O(d) | d = n, the discs: 2^d − 1 disc moves; `Tower.push()` and `Tower.pop()` are O(1) |
| `sorting_animate.Shelf.pop(key)`, `Shelf.insert(key, b)` | O(n − key) | O(n − key) | n = blocks on the shelf; every block after `key` slides over by one |
| `sorting_animate.isort(shelf)` | O(n²) | O(n) | Every block is popped and reinserted even when it is already in place, so a sorted shelf still costs O(n²) moves |
| `sorting_animate.ssort(shelf)` | O(n²) | O(n) | O(n²) comparisons on every input; no moves on a sorted shelf |
| `sorting_animate.qsort(shelf, left, right)` | O(n² log n) average, O(n³) worst | O(n) | Leftmost pivot, so a sorted or reversed shelf takes O(n²) comparisons. Each block moved past the pivot slides the rest of the shelf, so a reversed shelf costs O(n³) moves |
| `lindenmayer.replace(seq, replacementRules, n)` | O(M) | O(M) | M = characters in the n + 1 successive strings |
| `penrose.inflatekite(l, n)`, `penrose.inflatedart(l, n)` | O((2 + √2)^L) | O(φ^(2L)) | L = n. A tile is reached along more than one path, so the recursion outgrows the tiling; `tiledict` keeps one entry per position and heading. φ is the golden ratio |
| `penrose.sun(l, n)`, `penrose.star(l, n)` | O((2 + √2)^L) | O(φ^(2L)) | Five inflations |
| `penrose.draw(l, n, th=2)` | O(z) | O(z) | z = tiles in `tiledict`; one stamp each, and every stamp stays on the canvas |
| `rosette.mn_eck(p, ne, sz)` | O(t²) | O(t) | t = ne; t − 1 clones of `p`, then t steps of every turtle |
| `planet_and_moon.GravSys.start()` | O(p²) per step | O(p) per step | p = bodies; 10,000 steps, each computing every body's acceleration from every other. A pen-down body's trail stays on the canvas |

### Demos

Every demo's `main()` but `round_dance`'s is O(1) time and O(1) space: the sizes below are written
into its source.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `bytedesign.main()` | O(1) | O(1) | Draws under `tracer(0)` with an `update()` after each piece; returns its runtime |
| `chaos.main()` | O(1) | O(1) | Three 80-step orbits, then 100 `setworldcoordinates()` calls, each rescaling every item; returns `"Done!"` |
| `clock.main()` | O(1) | O(1) | Returns `"EVENTLOOP"`; `tick()` then moves the hands every 100 ms until STOP |
| `colormixer.main()` | O(1) | O(1) | Returns `"EVENTLOOP"`; each drag recolours the background |
| `forest.main()` | O(1) | O(1) | Three `forest.tree()` generators of levels 6, 7 and 5, advanced one branch each in turn; returns its runtime. Any exception ends only the tree it came from, so one STOP ends one tree and the others go on |
| `fractalcurves.main()` | O(1) | O(1) | A filled level-6 Hilbert curve, a 3-second `sleep()`, then two level-4 Koch figures; returns both runtimes |
| `lindenmayer.main()` | O(1) | O(1) | Two kolam patterns after three `replace()` passes each, with a 3-second `sleep()` between; returns `"Done!"` |
| `minimal_hanoi.main()` | O(1) | O(1) | Returns `"EVENTLOOP"`; the space bar runs `hanoi()` on 6 discs |
| `nim.main()` | O(1) | O(1) | 93 stick turtles; returns `"EVENTLOOP"`. The computer's reply sleeps 0.5 s plus 0.2 s per stick it takes |
| `paint.main()` | O(1) | O(1) | Returns `"EVENTLOOP"`; each left click is one `goto()`, and a fill stays open until the right button lifts the pen |
| `peace.main()` | O(1) | O(1) | Seven stripes and a circle; returns `"Done!"` |
| `penrose.main()` | O(1) | O(1) | Levels 0 to 7 of `sun` and of `star`, each padded with `sleep()` to take at least 2 s, then level 8; prints the tile count of each and returns `"Done"` |
| `planet_and_moon.main()` | O(1) | O(1) | `GravSys.start()` with 3 bodies; returns `"Done!"` |
| `rosette.main()` | O(1) | O(1) | `mn_eck()` with 36 turtles, a 1-second `sleep()`, then undoes every turtle's buffered commands; returns its runtime |
| `round_dance.main()` | O(f) | O(1) | f = frames until a key is pressed; each frame moves 15 dancers. Returns `"DONE!"` only after the key |
| `sorting_animate.main()` | O(1) | O(1) | Ten blocks; returns `"EVENTLOOP"`, and keys run the three sorts or shuffle |
| `tree.main()` | O(1) | O(1) | `tree.tree()` over 10 levels: 1,024 turtles; returns its runtime |
| `two_canvases.main()` | O(1) | O(1) | Opens a second Tk window with two screens and returns `"EVENTLOOP"`; STOP does not close that window |
| `yinyang.main()` | O(1) | O(1) | Two halves of the symbol; returns `"Done!"` |

## Running the Demos

### The Viewer

`python -m turtledemo` opens the viewer. Its Examples menu comes from a listing of the package
directory, and loading an entry imports that module once and shows its source.

```python
import turtledemo.__main__ as viewer

names = viewer.getExampleEntries()  # O(e) - lists the package directory
assert 'tree' in names and 'yinyang' in names
assert '__main__' not in names and '__init__' not in names
assert len(names) == 19
```

### Stopping a Demo

START runs `main()` on the viewer's own thread, so the STOP button is only noticed while the demo
redraws the canvas. The demo then raises `turtle.Terminator` at its next screen update, which under
`tracer(1)` is its next drawing command. `forest` catches that exception, so STOP ends only the
tree being drawn. Under `tracer(0)` a move neither redraws nor checks for STOP; only `update()`
does both, so a demo such as `bytedesign`, which calls `update()` after each piece, stops at the
`update()` after the one that saw the click.

## Recursion Levels

### Hilbert and Koch Curves

Each level of `hilbert()` or `fractal()` calls itself four times, so one more level is four
times the moves. The undo buffer holds one entry per move or turn, which makes the growth visible
without a display.

```python
from turtle import Screen
from turtledemo.fractalcurves import CurvesTurtle

Screen().tracer(0)  # no frames; only the commands are counted

entries = []
for level in (3, 4):
    pen = CurvesTurtle()
    pen.hilbert(5, level, 1)  # O(4^L) moves and turns
    entries.append(pen.undobufferentries())

assert entries == [147, 595]  # 4^L - 1 moves plus the turns, x4 per level
```

### Trees That Clone Turtles

`tree.tree()` and `forest.tree()` both draw a tree one level at a time, cloning a turtle at every
fork, so the turtles on the screen double (or multiply by the branch count) with every level.
`tree.tree()` is written as a generator but never yields: the whole tree is drawn inside the first
`next()`. `forest.tree()` yields once per branch, which is how `forest.main()` grows three trees
side by side. `tree.py` turns off the undo buffer first, since every clone copies it.

```python
from turtle import Screen, Turtle
from turtledemo.tree import tree

screen = Screen()
screen.tracer(0)
pen = Turtle()
pen.setundobuffer(None)

growth = tree([pen], 200, 65, 0.6375)  # O(1) - nothing drawn yet
assert list(growth) == []  # O(2^L) - the whole tree, drawn in the first next()
assert len(screen.turtles()) == 1024  # 2^10 turtles, all still on the screen
```

### Penrose Inflation

`inflatekite()` and `inflatedart()` split each tile into smaller kites and darts, and reach many
tiles more than once, so the recursion grows by 2 + √2 per level while the tiling it records
grows by about φ² ≈ 2.618. `draw()` then stamps each recorded tile once.

```python
from turtle import Screen
from turtledemo import penrose

Screen().tracer(0)
counts = []
for level in (4, 5):
    penrose.tiledict = {}
    penrose.sun(300, level)  # O((2 + √2)^L) recursive calls
    counts.append(len(penrose.tiledict))  # O(φ^(2L)) distinct tiles

assert 2.5 < counts[1] / counts[0] < 3  # about φ² per level
```

## Sorting on a Shelf

`sorting_animate` animates its sorts on a `Shelf`, a list whose `pop()` and `insert()` slide every
later block along by one. That turns each element moved into O(n) moves, and it makes the
quicksort's worst case cubic in moves.

```python
from turtle import Screen
from turtledemo import sorting_animate as sa

Screen().tracer(0)

class CountingBlock(sa.Block):
    moves = 0

    def setx(self, x):
        CountingBlock.moves += 1
        super().setx(x)

def horizontal_moves(sort, sizes):
    shelf = sa.Shelf(-200)
    for size in sizes:
        shelf.push(CountingBlock(size))
    CountingBlock.moves = 0
    sort(shelf)
    assert [block.size for block in shelf] == sorted(sizes)
    return CountingBlock.moves

def quicksort(shelf):
    sa.qsort(shelf, 0, len(shelf) - 1)

in_order = list(range(1, 11))
backwards = in_order[::-1]

assert horizontal_moves(sa.ssort, in_order) == 0  # nothing out of place
assert horizontal_moves(sa.isort, in_order) == 81  # O(n^2) even when sorted
assert horizontal_moves(quicksort, backwards) == 822  # O(n^3) worst case
```

## Lindenmayer Systems

`replace()` rewrites every character on each pass, and both of the demo's rule sets make the
string about four times longer per pass. Its cost is the characters of all the strings it builds,
which the last one dominates.

```python
from turtledemo.lindenmayer import replace

rules = {'b': 'b+f+b--f--b+f+b'}
lengths = [len(replace('b--f--b--f', rules, n)) for n in range(5)]  # O(M)

assert lengths == [10, 38, 150, 598, 2390]
```

## Performance Best Practices

✅ **Do**:

- Count what one more level costs before raising a demo's level: x4 for `hilbert()` and
  `fractal()`, x2 or more for the trees, 2 + √2 for Penrose inflation
- Call `setundobuffer(None)` before cloning many turtles, as `tree.py` does
- Replace `time.sleep` before importing `fractalcurves`, `lindenmayer`, `penrose` or `rosette` to
  run their `main()` without its pauses; `penrose.main()` otherwise takes at least 34 seconds

❌ **Avoid**:

- Scaling `sorting_animate` up to many blocks: every displaced block slides the rest of the
  shelf, so the quicksort's worst case is O(n³) moves
- Expecting STOP to interrupt a demo that draws under `tracer(0)` between its `update()` calls

## Related Modules

- **[turtle](turtle.md)** - what each command, frame and clone the demos issue costs
- **[tkinter](tkinter.md)** - the toolkit behind the viewer and every turtle screen
