# curses Module Complexity

The `curses` package prices three separate things, and confusing them is where
terminal applications lose their speed.

Allocating a window costs its whole cell array. Editing cells is local work
against that array, and reaches the terminal only where the window was told to
push each change out as it happens. Otherwise the update step is what talks to
the terminal, and it writes the cells that actually differ from what it
believes the screen already shows.

Four costs follow from that split. Batching every window through
`noutrefresh()` and one `doupdate()` runs the screen diff once instead of once
per window. A derived window shares its parent's cells, so `derwin()` is priced
in rows where `newwin()` is priced in cells. `instr()` and `getstr()` stop at a
fixed byte ceiling that no argument raises, and that ceiling moved on 3.14. And
`curses.panel` charges for the whole deck twice over: reordering it reconciles
the panel that moved against every other one, and handing back a panel object
walks a module-global list of every live panel.

## Complexity Reference

Size variables: r, c = a window's rows and columns, so r·c is its cells; R, C =
the terminal's rows and columns, which `curses.LINES` and `curses.COLS` report;
d = cells whose contents differ between the virtual screen and the physical
screen when the update runs; n = characters or cells an operation is asked to
span; W = cells summed over every window curses currently holds; o = cells two
windows overlap in; a = ancestors above a derived window; p = panel objects
alive in the process; h = rows two panels can overlap in; s = bytes in a
terminfo capability string; e = bytes in the terminal's terminfo description.

### Initialization and teardown

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `initscr()` | O(R·C) | O(R·C) | Allocates `stdscr` and the physical-screen image, then copies the `ACS_*` names plus `LINES` and `COLS` from `_curses` onto the `curses` package. None of those names exists before the first call |
| `endwin()` | O(1) | O(1) | Restores the terminal modes. The windows survive, and a later `refresh()` resumes curses |
| `isendwin()` | O(1) | O(1) | |
| `wrapper(func, /, *args, **kwds)` | O(R·C) + func | O(R·C) | `initscr()`, `noecho()`, `cbreak()`, `keypad(1)` and `start_color()`, then the call. Whether `func` returned or raised, the `finally` puts back `keypad(0)`, `echo()` and `nocbreak()` and calls `endwin()` - which is why a traceback stays readable. `start_color()` has no inverse and is not undone |
| `setupterm(term=None, fd=-1)` | O(e) | O(e) | Reads and parses the terminfo entry from the database. `initscr()` calls it |
| `use_env(flag)` | O(1) | O(1) | On, the size comes from `LINES` and `COLUMNS` where they are set, and from the terminal otherwise. Off, it comes from the terminfo entry, whatever the terminal is really doing. Set it before `setupterm()` or `initscr()` |
| `filter()` | O(1) | O(1) | Restricts curses to the one line the cursor starts on. Call it before `initscr()` |
| `error` | — | — | Most wrappers turn the C library's `ERR` into this, which is how a write past a window's edge surfaces. A few return a sentinel instead - `getch()` gives `-1`, `tigetnum()` gives a negative number |
| `ncurses_version` | O(1) | O(1) | A named tuple of `major`, `minor`, `patch` |

### Terminal modes and input settings

Every entry here sets a flag or reads one back. None of them scans a window.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `cbreak()` / `nocbreak()`, `raw()` / `noraw()` | O(1) | O(1) | |
| `echo()` / `noecho()`, `nl()` / `nonl()` | O(1) | O(1) | |
| `halfdelay(tenths)` | O(1) | O(1) | cbreak with a read timeout |
| `qiflush()` / `noqiflush()`, `intrflush(win, flag)` | O(1) | O(1) | |
| `typeahead(fd)` | O(1) | O(1) | `-1` disables the check that aborts a slow update when input is waiting |
| `meta(flag)` | O(1) | O(1) | |
| `curs_set(visibility)` | O(1) | O(1) | Returns the previous visibility |
| `napms(ms)` | blocks for ms | O(1) | The calling thread sleeps |
| `delay_output(ms)` | O(1) | O(1) | Pays the pause with padding characters where the terminal has one to send, and sleeps where it does not |
| `beep()` / `flash()` | O(1) | O(1) | |
| `ungetch(ch)` / `unget_wch(ch)` | O(1) | O(1) | |
| `flushinp()` | O(1) | O(1) | Discards unread input, including anything `ungetch()` pushed |
| `def_prog_mode()` / `def_shell_mode()` | O(1) | O(1) | |
| `reset_prog_mode()` / `reset_shell_mode()` | O(1) | O(1) | |
| `savetty()` / `resetty()` | O(1) | O(1) | |
| `get_escdelay()` / `set_escdelay(ms)` | O(1) | O(1) | |
| `get_tabsize()` / `set_tabsize(size)` | O(1) | O(1) | |
| `getsyx()` / `setsyx(y, x)` | O(1) | O(1) | The virtual screen's cursor, which the next `doupdate()` leaves the terminal at |
| `keyname(k)` / `unctrl(ch)` | O(1) | O(1) | Both return `bytes`. `unctrl` renders the meta bit as an `M-` prefix, where `curses.ascii.unctrl` uses `!` and returns `str` |
| `has_key(k)` | O(1) | O(1) | Importing `curses.has_key` binds the module of that name over this function, which then raises TypeError when called |
| `erasechar()` / `killchar()` | O(1) | O(1) | |
| `baudrate()` / `termattrs()` / `longname()` / `termname()` | O(1) | O(1) | |
| `has_colors()` / `can_change_color()` | O(1) | O(1) | |
| `has_extended_color_support()` | O(1) | O(1) | |
| `has_ic()` / `has_il()` | O(1) | O(1) | |
| `update_lines_cols()` | O(1) | O(1) | Re-reads `LINES` and `COLS` onto the module |
| `is_term_resized(nlines, ncols)` | O(1) | O(1) | Compares against the current size; no allocation |
| `resize_term(nlines, ncols)` | O(W) | O(W) | Visits every window curses holds, not just `stdscr`, and reallocates the ones the new size reaches. W counts the old cells and the new ones, so growing a screen costs more than the size it started at |
| `resizeterm(nlines, ncols)` | O(W) | O(W) | `resize_term()` plus repositioning and a queued `KEY_RESIZE` |

### Colours and mouse

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `start_color()` | O(1) | O(1) | Also copies `COLORS` and `COLOR_PAIRS` onto the `curses` package; neither exists before the call |
| `use_default_colors()` | O(1) | O(1) | The same call underneath with `-1, -1`, and the only spelling available before 3.14 |
| `assume_default_colors(fg, bg)` | O(1) | O(1) | Python 3.14 and later. Before that only `use_default_colors()` is exposed |
| `pair_content(pair_number)` | O(1) | O(1) | |
| `init_pair(pair_number, fg, bg)` | O(R·C) | O(1) | Scans the screen for cells carrying the pair. Where the pair is one the screen is painted in, it marks them, and the next update repaints those cells instead of diffing. The call itself writes nothing |
| `init_color(color_number, r, g, b)` / `color_content(color_number)` | O(1) | O(1) | `init_color` needs `can_change_color()` |
| `color_pair(pair_number)` / `pair_number(attr)` | O(1) | O(1) | Bit shifts between a pair number and the attribute carrying it |
| `mousemask(mousemask)` | O(1) | O(1) | Returns `(availmask, oldmask)`; an unsupported event silently drops out of the available mask |
| `mouseinterval(interval)` | O(1) | O(1) | Returns the previous interval |
| `getmouse()` / `ungetmouse(id, x, y, z, bstate)` | O(1) | O(1) | `getmouse()` pops the event `KEY_MOUSE` announced |

### Terminfo

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `tigetflag(capname)` / `tigetnum(capname)` | O(1) | O(1) | Neither raises. A capability this terminal lacks gives `0` and `-1`; a name that is not a capability of that kind at all gives `-1` and `-2` |
| `tigetstr(capname)` | O(s) | O(s) | s = bytes in a capability string. It is copied out of the entry; the database is not scanned. `None` where the terminal lacks it |
| `tparm(str[, ...])` | O(s) | O(s) | The capability string is interpreted once per call |
| `putp(string)` | O(s) | O(1) | Writes to `stdout`, outside the virtual screen curses is tracking |

### window: creation

`curses.window` cannot be instantiated; every window comes from one of these.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `newwin(nlines, ncols[, begin_y, begin_x])` | O(r·c) | O(r·c) | Allocates the cell array. `0` for a dimension means "to the edge of the screen" |
| `newpad(nlines, ncols)` | O(r·c) | O(r·c) | A window with no screen position, and free of the screen's size limit. It is pushed out through the six-argument `refresh()` or `noutrefresh()` |
| `window.subwin(...)` / `window.derwin(...)` / `window.subpad(...)` | O(r) | O(r) | Only the row pointers are new; the cells are the parent's, so a write through either is visible in the other and the column count does not enter the bound. `subwin` places the child by screen coordinates, `derwin` and `subpad` by coordinates within the parent |
| `window.resize(nlines, ncols)` | O(r·c) | O(r·c) | |
| `window.mvwin(new_y, new_x)` | O(r) | O(1) | Moves the window on the screen and marks its lines to go out again |
| `window.mvderwin(y, x)` | O(r) | O(1) | Moves the view over the parent's cells, which means rebinding one row pointer per row |
| `window.putwin(file)` | O(r·c) | O(1) | Writes a header and every cell, so the file grows with the window's area |
| `getwin(file)` | O(r·c) | O(r·c) | Rebuilds the window `putwin()` wrote |
| `window.encoding` | O(1) | O(1) | The codec a single non-ASCII character is folded through by `insch()`, `echochar()`, `hline()`, `vline()` and the background calls. On a build with wide-character support `addch()` and `addstr()` take a wide path instead and never reach it; without one, `addstr()` encodes through it too. It starts at the locale's |

### window: writing cells

These edit the window's own array and leave the next update to decide what
showing it costs, provided the window is in the default modes. `echochar()`
refreshes as it writes; under `immedok(True)` every write below refreshes too;
and under `syncok(True)` every write also propagates touches up the chain of
ancestors, at `syncup()`'s cost.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `window.addch(ch[, attr])` | O(1) | O(1) | For an ordinary character that fits. A tab, a newline, or a write at the last cell of a scrolling window moves the line or the whole window instead, at that operation's cost |
| `window.insch(ch[, attr])` | O(c) | O(1) | Shifts the rest of the line right |
| `window.echochar(ch[, attr])` | O(1) + one update | O(1) | `addch()` followed by a refresh, which also carries out whatever else was pending in the window |
| `window.addstr(str[, attr])` / `window.addnstr(str, n[, attr])` | O(len(str) + n) | O(len(str)) for a `str` | n = characters written, which `addnstr` caps. A `str` argument is converted whole - to wide characters, or to bytes on a narrow build - before any of it is written, so a long string with a small `n` still pays for the conversion. Bounds a window that does not scroll. Wrapping past the last line costs a `scroll()` each time it happens, ordinary characters included; a newline also clears the rest of its own line and a tab moves to the next stop - the same prices `addch()` pays |
| `window.insstr(str[, attr])` / `window.insnstr(str, n[, attr])` | O(len(str) + n + c) | O(len(str)) for a `str` | The same conversion, and the rest of the line shifts right. These never scroll |
| `window.hline(ch, n)` / `window.vline(ch, n)` | O(n) | O(1) | |
| `window.chgat(n, attr)` | O(n) | O(1) | Re-attributes cells without rewriting their characters |
| `window.border(...)` / `window.box(...)` | O(r + c) | O(1) | The perimeter only |
| `window.delch([y, x])` | O(c) | O(1) | |
| `window.deleteln()` / `window.insertln()` / `window.insdelln(nlines)` | O(r·c) | O(1) | Every line below the cursor moves |
| `window.scroll([lines])` | O(r·c) | O(1) | Needs `scrollok(True)` |
| `window.erase()` | O(r·c) | O(1) | Blanks every cell |
| `window.clear()` | O(r·c) | O(1) | `erase()` plus `clearok(True)`, so the next update repaints rather than diffing |
| `window.clrtoeol()` / `window.clrtobot()` | O(c) / O(r·c) | O(1) | |
| `window.bkgd(ch[, attr])` | O(r·c) | O(1) | Rewrites the background of every existing cell |
| `window.bkgdset(ch[, attr])` | O(1) | O(1) | Applies to cells written afterwards only, which is the whole difference from `bkgd()` |
| `window.overlay(destwin[, ...])` / `window.overwrite(destwin[, ...])` | O(o) | O(1) | `overlay` leaves the destination alone where the source cell is blank; `overwrite` copies the blank over it |
| `window.attron(attr)` / `attroff(attr)` / `attrset(attr)` | O(1) | O(1) | |
| `window.standout()` / `window.standend()` | O(1) | O(1) | |
| `window.move(new_y, new_x)` | O(1) | O(1) | |

### window: reading cells and input

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `window.inch([y, x])` | O(1) | O(1) | The cell as an integer: the character byte under `A_CHARTEXT`, the rendition under `A_ATTRIBUTES` |
| `window.instr([y, x][, n])` | O(min(n, cap)) | O(min(n, cap)) | cap is 2047 bytes on 3.14 and 1023 before it. A larger `n` is silently clamped, so this can never read a wide row whole |
| `window.getstr([y, x][, n])` | O(min(n, cap)) + the input | O(min(n, cap)) | The same ceiling on the result. It bounds what comes back, not the keystrokes read to get there: line editing and characters past the ceiling are still processed |
| `window.getch([y, x])` | O(1) + the wait | O(1) | `nodelay(True)` makes the wait zero and `timeout(ms)` bounds it; with nothing to read this returns `-1`. A window holding changes that have not been pushed out is refreshed first, at that cost |
| `window.get_wch([y, x])` / `window.getkey([y, x])` | O(1) + the wait | O(1) | The same wait, but with nothing to read these two raise `curses.error` rather than returning a sentinel |
| `window.getyx()` / `getbegyx()` / `getmaxyx()` / `getparyx()` | O(1) | O(1) | `getparyx()` is `(-1, -1)` for a window that has no parent |
| `window.getbkgd()` | O(1) | O(1) | |
| `window.enclose(y, x)` | O(1) | O(1) | Whether a screen position falls inside the window |

### window: the update path

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `window.noutrefresh()` | O(r + cells on touched lines), plus `syncdown()` for a derived window | O(1), O(a) for a derived window | Copies the window into the virtual screen, skipping the lines nothing touched. No terminal traffic either way. A derived window takes its ancestors' touches on first, so a small window under a deep chain is not cheap |
| `doupdate()` | O(R·C) | O(1) | Diffs the virtual screen against the physical one and writes output for the d cells that differ, plus whatever cursor movement that takes. With no difference and the cursor where it was, nothing is written |
| `window.refresh()` | `noutrefresh()` + O(R·C) | O(1), O(a) for a derived window | `noutrefresh()` then `doupdate()`, so every window refreshed this way pays the screen diff again |
| `window.redrawwin()` / `window.redrawln(beg, num)` | O(r·c) / O(num·c) | O(1) | Discards what curses believes the terminal shows of those cells, so the next update writes them in full where `touchwin()` produces no output at all. Priced in cells, where touching is priced in lines |
| `window.touchwin()` / `window.touchline(start[, count])` | O(r) / O(count) | O(1) | Marks lines changed in the window. The update still diffs against the physical screen, so touching alone produces no output |
| `window.untouchwin()` | O(r) | O(1) | |
| `window.is_wintouched()` / `window.is_linetouched(line)` | O(r) / O(1) | O(1) | |
| `window.syncup()` / `window.syncdown()` | O(rows summed over the chain) | O(a) | Carry touches up or down the chain of derived windows. Each level is told which of its lines changed, so a deep chain of tall windows costs more than a deep chain of short ones, and the walk itself is one frame per level |
| `window.cursyncup()` | O(a) | O(1) | Carries only the cursor position, so this one is the depth alone and the rows do not enter it |
| `window.clearok(flag)` | O(1) | O(1) | The next update repaints the whole screen instead of diffing |
| `window.immedok(flag)` | O(1) | O(1) | Makes every later write refresh immediately, turning one update per frame into one per write |
| `window.idlok(flag)` / `window.idcok(flag)` | O(1) | O(1) | Whether the update may use the terminal's insert/delete line and character capabilities |
| `window.leaveok(flag)` / `window.scrollok(flag)` / `window.syncok(flag)` | O(1) | O(1) | |
| `window.keypad(flag)` / `window.nodelay(flag)` / `window.notimeout(flag)` | O(1) | O(1) | |
| `window.timeout(delay)` / `window.setscrreg(top, bottom)` | O(1) | O(1) | |

### curses.ascii

Every function tests or masks one character code and returns at once. `c` may
be a one-character `str` or an `int`; nothing here allocates more than the
single-character result.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `isalnum(c)` / `isalpha(c)` / `isascii(c)` / `isblank(c)` | O(1) | O(1) | |
| `iscntrl(c)` / `isctrl(c)` / `ismeta(c)` | O(1) | O(1) | `iscntrl` counts `DEL` as a control character; `isctrl` stops below `SP` |
| `isdigit(c)` / `isxdigit(c)` / `isgraph(c)` / `isprint(c)` | O(1) | O(1) | |
| `islower(c)` / `isupper(c)` / `ispunct(c)` / `isspace(c)` | O(1) | O(1) | |
| `ascii(c)` / `ctrl(c)` / `alt(c)` | O(1) | O(1) | Mask to 7 bits, to 5 bits, or set the meta bit. The result is `str` for a `str` argument and `int` for an `int` |
| `unctrl(c)` | O(1) | O(1) | Always `str`, with `!` for the meta bit, where `curses.unctrl` returns `bytes` and uses `M-` |
| `controlnames` | O(1) | O(1) | The 33 names `NUL` through `US`, then `SP`, indexed by code. Tab and newline appear as `HT` and `LF` |

### curses.panel

Two separate costs run through this module, and both grow with p. Changing the
deck makes curses reconcile the panel against the others in it. Separately, the
module keeps one global list of every live panel object, newest first, and
walks it whenever a call has to hand a panel back; that list is in creation
order, not deck order, so its half of the cost tracks how long ago the wanted
panel was made rather than where it sits.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `new_panel(win)` | O(1) | O(1) | Puts the panel on top of the deck. Letting the last reference to a panel go is the expensive half: taking it back out of the deck is O(p) |
| `panel.top()` / `panel.bottom()` / `panel.hide()` | O(p) | O(1) | Each reorders the deck and reconciles it again |
| `panel.move(y, x)` | O(p + r) | O(1) | The window moves, at `mvwin()`'s cost, and what the panel covers changes, so the deck is reconciled too |
| `panel.show()` / `panel.hidden()` / `panel.window()` | O(1) | O(1) | `show()` costs the same whatever the deck holds, which is what separates it from `hide()` |
| `panel.set_userptr(obj)` / `panel.userptr()` | O(1) | O(1) | `userptr()` raises `curses.panel.error` when nothing was set |
| `top_panel()` / `bottom_panel()` | O(p) | O(1) | Both walk the global list. `top_panel()` is usually the newest panel and so found at once; `bottom_panel()` is usually the oldest and so found last |
| `panel.above()` / `panel.below()` | O(p) | O(1) | The same walk |
| `panel.replace(win)` | O(p) | O(1) | The walk, then the swap |
| `update_panels()` | O(p²·(1 + h)) plus a `noutrefresh()` per panel | O(1), or the deepest staged window's O(a) | h = rows a pair of panels overlaps in. Every panel is reconciled against every other over the rows they share, and every panel is then staged into the virtual screen, so its own cells - and its ancestors, if it is a derived window - count too |
| `error` | — | — | Distinct from `curses.error` |

### curses.textpad

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `rectangle(win, uly, ulx, lry, lrx)` | O(height + width) | O(1) | Two `hline`s, two `vline`s and the four corners. The lower-right corner must be inside the window |
| `Textbox(win, insert_mode=False)` | O(1) | O(1) | Also sets `keypad(1)` on the window |
| `Textbox.do_command(ch)` | O(1) to O(r·c) for an edit, `refresh()` for `Ctrl-L` | O(1), the window's for `Ctrl-L` | A printable key is O(1) in overwrite mode; in insert mode it pushes the rest of the line right a cell at a time, and past the end of a line it carries on into the next. The cursor and kill keys scan a line for its last non-blank, O(c). `Ctrl-O` and `Ctrl-K` on an empty line move every line below. `Ctrl-L` is the one that leaves the box: it refreshes, which is priced against the screen and not the box |
| `Textbox.gather()` | O(r·c) | O(r·c) | Reads every cell back one at a time. With `stripspaces` set it still scans each row to find where the blanks begin |
| `Textbox.edit(validate=None)` | one `do_command` and refresh per key, then `gather()` | O(r·c) | Blocks on `getch()` until `do_command()` returns 0, which `Ctrl-G` makes it do |
| `Textbox.stripspaces` | O(1) | O(1) | Whether trailing blanks are dropped from `gather()` and where `Ctrl-E` lands. On by default |

## One doupdate, not one refresh per window

`window.refresh()` is `noutrefresh()` followed by `doupdate()`. The first half
is proportional to what the window itself touched; the second diffs the whole
virtual screen against the physical one. Refreshing several windows separately
runs that diff once each where one run would do, and shows every intermediate
screen on the way; batching updates once, from the final virtual screen.

```python
import curses

def main(stdscr):
    rows = [curses.newwin(1, 20, y, 0) for y in range(5)]  # O(r*c) each
    for y, win in enumerate(rows):
        win.addstr(0, 0, f"row {y}")                       # O(n), no terminal traffic

    # One screen diff for all five windows, not five.
    for win in rows:
        win.noutrefresh()                                  # O(touched cells)
    curses.doupdate()                                      # O(R*C), writes the diff

    # Nothing changed since, so the next update has nothing to write.
    curses.doupdate()

    # A second refresh of an untouched window is not free either way: it still
    # runs the diff. Only the touch flags make it cheap.
    assert rows[0].is_wintouched() is False
    rows[0].touchwin()
    assert rows[0].is_wintouched() is True

    # Touching marks the window, not the terminal: the update still compares
    # against what the screen shows, and finds no difference.
    rows[0].noutrefresh()
    curses.doupdate()

    # redrawwin() is the one that forces bytes out, by discarding what curses
    # believes the terminal is displaying.
    rows[0].redrawwin()
    rows[0].refresh()

curses.wrapper(main)
```

## Derived windows share their parent's cells

`newwin()` allocates rows × columns of storage. `derwin()`, `subwin()` and
`subpad()` allocate a row pointer per row and point it into the parent, so
their cost does not grow with the width, and a write through one is a write
through the other.

```python
import curses

def main(stdscr):
    parent = curses.newwin(10, 40, 0, 0)     # O(r*c)
    view = parent.derwin(3, 10, 2, 5)        # O(r), and shares parent's cells

    view.addstr(0, 0, "ZZZ")
    assert parent.instr(2, 5, 3) == b"ZZZ"   # the parent already has it

    parent.addstr(2, 5, "QQQ")
    assert view.instr(0, 0, 3) == b"QQQ"     # and the traffic runs both ways

    # derwin() places the child inside the parent; subwin() uses screen
    # coordinates for the same spot.
    assert view.getbegyx() == (2, 5)
    assert view.getparyx() == (2, 5)
    assert parent.subwin(3, 10, 2, 5).getbegyx() == (2, 5)

    # A pad is free of the screen's size limit, so it can be far larger than
    # the terminal - and it costs its whole area.
    pad = curses.newpad(200, 200)            # O(r*c)
    assert pad.getmaxyx() == (200, 200)

curses.wrapper(main)
```

## instr() and getstr() stop at a fixed ceiling

Both read into a buffer whose size the module fixes. The `n` argument can only
lower it. A row wider than the ceiling cannot be read back in one call, and the
ceiling itself moved on 3.14.

```python
import curses
import sys

CAP = 2047 if sys.version_info >= (3, 14) else 1023

def main(stdscr):
    pad = curses.newpad(2, 4000)
    pad.addstr(0, 0, "z" * 3000)

    # Asking for more than the ceiling is clamped, not an error.
    assert len(pad.instr(0, 0, 3000)) == CAP   # O(min(n, CAP))
    assert len(pad.instr(0, 0)) == CAP         # the default is the ceiling too
    assert len(pad.instr(0, 0, 10)) == 10      # a smaller n does apply

    # inch() is the way to read one cell without the ceiling in play.
    assert pad.inch(0, 0) & curses.A_CHARTEXT == ord("z")

curses.wrapper(main)
```

## Reordering a panel deck costs the whole deck

Raising a panel, lowering one, hiding one and moving one all make curses
reconcile that panel against every other panel in the deck, and so does letting
the last reference to one go. Separately, the calls that hand a panel object
back search a module-global list that `new_panel()` prepends to, so the one
that finds the oldest panel searches the whole of it.

What is left costs the same whatever the deck holds: creating a panel, showing
a hidden one again, and reading back `hidden()`, `window()` or the user
pointer. `show()` does put its panel on top; it is only the reconciliation it
skips.

```python
import curses
import curses.panel

def main(stdscr):
    windows = [curses.newwin(3, 10, y, y) for y in range(4)]
    panels = [curses.panel.new_panel(w) for w in windows]   # O(1) each

    # The deck is newest-on-top.
    assert curses.panel.top_panel() is panels[-1]           # O(p), a list walk
    assert curses.panel.bottom_panel() is panels[0]         # O(p), a list walk
    assert panels[0].below() is None                        # O(p), a list walk

    panels[0].top()                                         # O(p), a deck change
    assert curses.panel.top_panel() is panels[0]

    panels[0].hide()                                        # O(p), a deck change
    assert panels[0].hidden() is True                       # O(1)
    assert panels[1].window() is windows[1]                 # O(1)
    assert curses.panel.top_panel() is panels[-1]

    panels[0].show()                                        # O(1)

    # update_panels() reconciles every panel against every other - O(p^2) - and
    # leaves the writing to doupdate().
    curses.panel.update_panels()                            # O(p^2)
    curses.doupdate()                                       # O(R*C), writes the diff

curses.wrapper(main)
```

## Reading a box back costs its area

`Textbox.gather()` reads the window one cell at a time, and with `stripspaces`
on it also scans each row for the last non-blank. Both terms are the window's
area, so the cost is the box's size rather than the amount typed into it.

```python
import curses
import curses.ascii
import curses.textpad

def main(stdscr):
    win = curses.newwin(3, 20, 0, 0)
    box = curses.textpad.Textbox(win)        # O(1)

    for ch in "hello":
        box.do_command(ord(ch))              # O(1) here; O(c) in insert mode

    # stripspaces trims each row to one blank past its last non-blank, and
    # drops the all-blank rows entirely - newlines included. The boundary is
    # the text's, so parking the cursor elsewhere does not move it.
    win.move(2, 19)
    assert box.stripspaces == 1
    assert box.gather() == "hello \n"        # O(r*c)

    box.stripspaces = 0
    assert box.gather() == "hello" + " " * 15 + "\n" + (" " * 20 + "\n") * 2

    # Ctrl-G is the key edit() stops on, and do_command reports it as 0.
    assert box.do_command(curses.ascii.BEL) == 0

    # curses.ascii never looks past the one character it is given.
    assert curses.ascii.isctrl(curses.ascii.BEL) is True
    assert curses.ascii.unctrl(1) == "^A"    # str, and '!' for the meta bit
    assert curses.unctrl(1) == b"^A"         # bytes, and 'M-' for it
    assert curses.ascii.controlnames[9] == "HT"

curses.wrapper(main)
```

## Related Documentation

- [tkinter Module](tkinter.md)
- [turtle Module](turtle.md)
