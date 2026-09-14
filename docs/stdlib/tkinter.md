# tkinter Module Complexity

The `tkinter` module wraps Tk. Almost every method on a widget, variable, image or font is one call into the Tcl interpreter: Python marshals the arguments, Tk does the work in C, and the result is converted back. A row's bound is therefore the Python marshalling plus what Tk's own data structure costs; drawing is never part of it, because Tk redraws at idle time and charges the visible area, not the call. Only `Tk()` needs a display: a `Tcl()` interpreter runs the `after` timers, variables and traces without one.

## Complexity Reference

Size variables: k = options passed in one call, each callable value registering one Tcl command; o = options a widget or item has, so a query with no arguments returns o of them; c = Tcl commands a widget has registered and not deleted - bound handlers, pending `after` calls, callable options; d = descendants of a widget; p = components in a window path name; n = entries, items or children a widget holds; m = characters, items or matches an operation touches or returns; L = lines in a `Text` widget; ℓ = characters on the line a `Text` edit lands on; t = traces on a variable; b = handlers bound to one event sequence; s = selected items; W = widgets in a window tree; D = the layout and drawing Tk has pending, proportional to the widgets relaid and the area redrawn; i = position of an item among its siblings; u = entries on an undo stack; P = pixels in an image; F = bytes in a file read; E = entries in a directory; w = time spent blocked in an event loop; e = events processed; f = the caller's own callback or profile code, whose cost is its own. n is per widget, not per application. A name in a bound that is not listed here, such as pending, tags or themes, counts the things it names.

Widget options reach Tk through one routine that rebuilds the argument tuple once per option, so every row below that takes widget options is O(k²) in Python. Option values are copied into Tcl at their own size, a list-valued one joined into one string first; the rows leave that size out, as they leave out the size of a value read back. k never exceeds o, and o is a few dozen at most, so this is never the term that matters; it is written out because the `ttk.Style` methods and the ttk item methods such as `Treeview.insert()` format their options in O(k), and that is the one place the two spellings differ in cost.

### Tk and Tcl

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Tk()` | O(F + f) | O(F) | Starts a Tcl interpreter and loads Tk, then runs the profile files `.Tk.tcl`, `.Tk.py`, `.<basename>.tcl` and `.<basename>.py` from the home directory, F bytes between them, at their own code's cost, unless Python runs with `-E`. The first `Tk()` becomes the default root that `StringVar()`, `Button()` and the module functions fall back to |
| `Tcl()` | O(F + f) | O(F) | The same interpreter without Tk: no display, no widgets, no `bind`, but `after`, `update()`, variables, traces and `register()` all work; `mainloop()` returns at once because no Tk window exists |
| `Tk.loadtk()` | O(1) | O(1) | Loads Tk into a `Tcl()` interpreter; a no-op once loaded |
| `Tk.readprofile(baseName, className)` | O(F + f) | O(F) | Sources the two `.tcl` files and `exec`s the two `.py` files, in a namespace holding every `tkinter` name |
| `Tk.destroy()` | O(d + c + n) | O(d) | Destroys every descendant first, c and n counted over the whole tree and a copy of each children list held on the way down, and forgets the default root if this was it |
| `Tk.report_callback_exception(exc, val, tb)` | O(depth) | O(depth) | Prints the traceback to stderr and stores it in the `sys.last_*` attributes; every exception but SystemExit that a callback raises ends here, not in the caller |
| `Tk.tk` / `Tk.master` / `Tk.children` | O(1) | O(1) | The interpreter object, `None`, and the dict of direct children by name; attributes `Tk` lacks are looked up on `Tk.tk` |
| `mainloop()` / `Misc.mainloop()` | O(w + e·(f + c) + D) | O(1) | Dispatches events until `quit()` or the last window closes; an `after` callback also deletes its command when it runs. The module function needs a default root |
| `Misc.quit()` | O(1) | O(1) | Sets a flag the loop checks after the current event |
| `Misc.update()` | O(e·(f + c) + D) | O(1) | Runs every pending event, timer and idle callback, then returns; the idle work includes the pending relayout and redraw |
| `Misc.update_idletasks()` | O(e·(f + c) + D) | O(1) | Idle callbacks only, which is where the relayout and redraws happen |
| `Misc.wait_variable(var)` / `Misc.wait_window(w)` / `Misc.wait_visibility(w)` | O(w + e·(f + c) + D) | O(1) | A nested event loop until the variable is written, the window destroyed or its visibility changed |
| `NoDefaultRoot()` | O(1) | O(1) | After it, every widget, variable or image created without a master raises RuntimeError |
| `getboolean(s)` / `getint` / `getdouble` | O(m) | O(m) | Parse m characters; the module function asks the default root's interpreter, and `getint` and `getdouble` are `int` and `float` |
| `Misc.getboolean(s)` / `Misc.getint(s)` / `Misc.getdouble(s)` / `Misc.getvar(name)` / `Misc.setvar(name, value)` | O(m + t·f) | O(m) | One conversion or one Tcl variable of m characters; `getvar()` and `setvar()` run the variable's traces |
| `Misc.info_patchlevel()` | O(1) | O(1) | Python 3.11+ |
| `TclError` / `TkVersion` / `TclVersion` / `wantobjects` | O(1) | O(1) | The exception every Tk error raises, the version floats, and the flag that makes results come back typed rather than as strings |

### Misc: callbacks and events

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Misc.register(func)` | O(1) | O(1) | Creates one Tcl command whose name embeds `id()` and the function name, appended to the widget's registry list |
| `Misc.deletecommand(name)` | O(c) | O(1) | Deletes the command and removes it from the list, which is scanned |
| `Misc.destroy()` | O(c) | O(1) | Deletes every command the widget registered; the widget classes override it to destroy the window and its descendants first |
| `Misc.after(ms, func, *args)` | O(pending) | O(1) | Registers one command and inserts the timer into Tcl's list, kept sorted by due time; the callback deletes its command when it fires, at O(c). `after(ms)` with no function blocks for ms without processing events |
| `Misc.after_idle(func, *args)` | O(1) | O(1) | Registers one command and appends it to the idle list |
| `Misc.after_cancel(id)` | O(pending + c) | O(1) | One `after info` round trip, which Tcl answers by walking its pending timers, then the registry scan; a falsy id raises ValueError |
| `Misc.after_info(id)` | O(pending) | O(pending) | Python 3.13+; Tcl walks its pending timers for the id, and without one returns them all |
| `Misc.bind(sequence, func, add)` / `Misc.bind_all()` / `Misc.bind_class(className, ...)` | O(b) | O(b) | One command per bound function; with `add` Tk copies the sequence's script to append the line, otherwise b is 1 |
| `Misc.bind(sequence)` / `Misc.bind()` | O(b + m) | O(b + m) | The sequence's script, one line per handler, or the widget's m bound sequences |
| `Misc.unbind(sequence, funcid)` / `Canvas.tag_unbind()` / `Text.tag_unbind()` | O(b + c) | O(b) | Python 3.13+ reads the sequence's script and rewrites it without funcid's line, then deletes the command; before 3.13 every handler on the sequence goes. Without funcid, one call clears the sequence |
| `Misc.unbind_all(sequence)` / `Misc.unbind_class(className, sequence)` | O(1) | O(1) | Clear the sequence's script; the commands stay registered |
| `Misc.bindtags(tagList)` | O(tags) | O(tags) | |
| `Misc.event_add(virtual, *sequences)` / `Misc.event_delete()` / `Misc.event_generate(sequence, **k)` | O(m + k² + b·f) | O(m + k) | `event_generate` delivers the event before returning unless `when=` defers it, so its handlers run inside the call |
| `Misc.event_info(virtual)` | O(m) | O(m) | The sequences behind one virtual event, or every virtual event |
| `Misc.focus_set()` / `Misc.focus_force()` / `Misc.tk_focusFollowsMouse()` | O(1) | O(1) | |
| `Misc.focus_get()` / `Misc.focus_displayof()` / `Misc.focus_lastfor()` / `Misc.grab_current()` | O(p) | O(p) | Resolve the returned path name to its widget |
| `Misc.tk_focusNext()` / `Misc.tk_focusPrev()` | O(W²) | O(W) | Walk the window tree from the widget until a widget accepts focus, listing the parent's children and searching them for the current widget at every step |
| `Misc.grab_set()` / `Misc.grab_set_global()` / `Misc.grab_release()` / `Misc.grab_status()` | O(1) | O(1) | |
| `Misc.clipboard_get()` / `Misc.clipboard_append(string)` / `Misc.clipboard_clear()` | O(m) | O(m) | The selection owner supplies the m characters, so `clipboard_get()` waits on it |
| `Misc.selection_get()` / `Misc.selection_handle(func)` / `Misc.selection_own()` / `Misc.selection_own_get()` / `Misc.selection_clear()` | O(m) | O(m) | `selection_handle` registers one command that Tk calls with an offset and a length, so f is charged per chunk |
| `Misc.option_add(pattern, value)` / `Misc.option_get(name, className)` | O(1) | O(1) | |
| `Misc.option_clear()` | O(m) | O(1) | Frees every entry of the option database and reloads the display's defaults |
| `Misc.option_readfile(fileName)` | O(F) | O(F) | Adds every entry of an F-byte resource file |
| `Misc.send(interp, cmd, *args)` | O(w) | O(1) | A round trip to another interpreter on the same display, blocked until it replies |
| `Misc.bell()` / `Misc.lower()` / `Misc.tkraise()` / `Misc.lift()` | O(1) | O(1) | |
| `Misc.tk_setPalette(*args, **k)` / `Misc.tk_bisque()` | O(W) | O(1) | Recolour every widget under the root through the option database |
| `Misc.tk_strictMotif(boolean)` | O(1) | O(1) | |
| `Misc.tk_busy_hold()` / `Misc.tk_busy_forget()` / `Misc.tk_busy_configure()` / `Misc.tk_busy_cget()` / `Misc.tk_busy_status()` | O(1) | O(1) | Python 3.13+ |
| `Misc.tk_busy_current(pattern)` | O(m) | O(m) | Python 3.13+; the m busy windows matching the pattern |
| `Misc.image_names()` / `Misc.image_types()` / `image_names()` / `image_types()` | O(images) | O(images) | `image_types()` is a fixed list; the module functions need a default root |

### Misc: configuration and window information

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Misc.configure(**k)` / `Misc.config()` / `Misc.__setitem__` | O(k² + t·f) | O(k) | Applies k options in one Tk call; each callable value registers a command that lives until the widget is destroyed, and a `variable` or `textvariable` is read at once, firing its traces |
| `Misc.configure()` / `Misc.keys()` | O(o) | O(o) | Tk returns every option's specification; `keys()` keeps the names |
| `Misc.cget(key)` / `Misc.__getitem__` | O(m) | O(m) | The value's m characters, converted |
| `Misc.nametowidget(name)` | O(p) | O(p) | Splits the name, then one dict lookup per component from the root or from this widget |
| `Misc.winfo_children()` | O(n·p) | O(n) | Asks Tk for the child names and resolves each from the root, skipping ones Tk owns such as menus |
| `Misc.winfo_x()` / `Misc.winfo_y()` / `Misc.winfo_width()` / `Misc.winfo_height()` / `Misc.winfo_reqwidth()` / `Misc.winfo_reqheight()` / `Misc.winfo_geometry()` / `Misc.winfo_vrootx()` / `Misc.winfo_vrooty()` / `Misc.winfo_vrootwidth()` / `Misc.winfo_vrootheight()` | O(1) | O(1) | Read from the window record; a size is 1 until the widget is mapped and `update_idletasks()` has run |
| `Misc.winfo_rootx()` / `Misc.winfo_rooty()` | O(p) | O(1) | Sum the offsets of every ancestor |
| `Misc.winfo_id()` / `Misc.winfo_name()` / `Misc.winfo_class()` / `Misc.winfo_parent()` / `Misc.winfo_pathname(id)` / `Misc.winfo_exists()` / `Misc.winfo_ismapped()` / `Misc.winfo_manager()` | O(1) | O(1) | |
| `Misc.winfo_toplevel()` / `Misc.winfo_viewable()` | O(p) | O(1) | Walk up the path |
| `Misc.winfo_screen()` / `Misc.winfo_screenwidth()` / `Misc.winfo_screenheight()` / `Misc.winfo_screenmmwidth()` / `Misc.winfo_screenmmheight()` / `Misc.winfo_screendepth()` / `Misc.winfo_screencells()` / `Misc.winfo_screenvisual()` / `Misc.winfo_server()` / `Misc.winfo_depth()` / `Misc.winfo_cells()` / `Misc.winfo_visual()` / `Misc.winfo_visualid()` / `Misc.winfo_colormapfull()` | O(1) | O(1) | |
| `Misc.winfo_pointerx()` / `Misc.winfo_pointery()` / `Misc.winfo_pointerxy()` / `Misc.winfo_containing(x, y)` / `Misc.winfo_pixels(number)` / `Misc.winfo_fpixels(number)` / `Misc.winfo_rgb(color)` / `Misc.winfo_atom(name)` / `Misc.winfo_atomname(id)` | O(1) | O(1) | The pointer queries and `winfo_containing()` are a round trip to the display server |
| `Misc.winfo_visualsavailable()` / `Misc.winfo_interps()` | O(m) | O(m) | Every visual of the screen, or every Tk interpreter on the display |
| `Misc.pack_slaves()` / `Misc.place_slaves()` / `Misc.grid_slaves(row, column)` | O(n) | O(n) | Every widget the manager holds; `grid_slaves()` filters by row or column after the scan |
| `Misc.pack_propagate(flag)` / `Misc.grid_propagate(flag)` / `Misc.grid_anchor(anchor)` / `Misc.grid_columnconfigure(index, **k)` / `Misc.grid_rowconfigure(index, **k)` | O(k² + m) | O(k) | A list of m indices configures each one |
| `Misc.grid_size()` / `Misc.grid_bbox()` | O(n) | O(1) | Tk recomputes the grid's extent from every managed widget |
| `Misc.grid_location(x, y)` | O(rows + columns) | O(1) | Scans the slot offsets |

### Pack, Grid and Place

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Pack.pack_configure(**k)` / `Pack.pack()` / `Grid.grid_configure(**k)` / `Grid.grid()` / `Place.place_configure(**k)` / `Place.place()` | O(n + k²) | O(k) | Hands the widget to the manager, which walks the container's list of managed widgets to append it; the layout itself runs once at idle time for the whole container, however many widgets were added before it |
| `Pack.pack_forget()` / `Grid.grid_forget()` / `Grid.grid_remove()` / `Place.place_forget()` | O(n) | O(1) | Unlinks the widget from the container's list of managed widgets, walked to find it; `grid_remove()` keeps the grid options for a later `grid()` with none |
| `Pack.pack_info()` / `Grid.grid_info()` / `Place.place_info()` | O(o) | O(o) | A dict of the manager's options for this widget |
| `Pack.propagate()` / `Pack.slaves()` / `Grid.bbox()` / `Grid.columnconfigure()` / `Grid.rowconfigure()` / `Grid.propagate()` / `Grid.size()` / `Grid.slaves()` / `Place.slaves()` | O(n + k²) | O(n) | The `Misc` container methods under their manager-local names, with the bounds above |
| `Grid.location(x, y)` | O(rows + columns) | O(1) | `Misc.grid_location()` under its manager-local name |

### Wm

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Wm.wm_title(string)` / `Wm.wm_geometry(newGeometry)` / `Wm.wm_iconname()` / `Wm.wm_state()` / `Wm.wm_withdraw()` / `Wm.wm_deiconify()` / `Wm.wm_iconify()` / `Wm.wm_resizable()` / `Wm.wm_minsize()` / `Wm.wm_maxsize()` / `Wm.wm_aspect()` / `Wm.wm_overrideredirect()` / `Wm.wm_transient()` / `Wm.wm_group()` / `Wm.wm_client()` / `Wm.wm_command()` / `Wm.wm_focusmodel()` / `Wm.wm_positionfrom()` / `Wm.wm_sizefrom()` / `Wm.wm_grid()` / `Wm.wm_frame()` / `Wm.wm_iconbitmap()` / `Wm.wm_iconmask()` / `Wm.wm_iconposition()` / `Wm.wm_iconwindow()` / `Wm.wm_manage()` / `Wm.wm_forget()` | O(1) | O(1) | One request to the window manager; each is also available without the `wm_` prefix, and the manager applies it asynchronously |
| `Wm.wm_attributes(**k)` | O(k) | O(k) | The query with no arguments returns every attribute, as a dict with `return_python_dict=True` from Python 3.13 |
| `Wm.wm_protocol(name, func)` | O(1) | O(1) | Registers one command; `WM_DELETE_WINDOW` defaults to `destroy()` on `Tk` and `Toplevel` |
| `Wm.wm_colormapwindows(*windows)` | O(m) | O(m) | One argument per window |
| `Wm.wm_iconphoto(default, *images)` | O(P) | O(P) | Converts every pixel of every image given into the window manager's icon format |

### Variable, StringVar, IntVar, DoubleVar and BooleanVar

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Variable(master, value, name)` / `StringVar()` / `IntVar()` / `DoubleVar()` / `BooleanVar()` | O(m + t·f) | O(m) | One Tcl variable, named `PY_VAR<n>` from a module counter unless a name is given; a value is copied in, firing the write traces an existing variable of that name has, and without a value an existing variable keeps its value and a new one gets the class default |
| `Variable.get()` / `Variable.set(value)` / `Variable.initialize(value)` / `StringVar.get()` / `IntVar.get()` / `DoubleVar.get()` / `BooleanVar.get()` / `BooleanVar.set()` | O(m + t·f) | O(m) | Copies the value across the interpreter boundary and runs the read or write traces; `IntVar.get()` accepts a float-valued string, `BooleanVar.get()` raises ValueError on anything Tcl cannot read as a boolean |
| `Variable.trace_add(mode, callback)` | O(1) | O(1) | Registers one command and one trace; the name it returns is the command |
| `Variable.trace_remove(mode, cbname)` | O(t² + c) | O(t) | Removes the trace, whose mode list must be the one given to `trace_add()` or nothing is removed, then lists the remaining traces at `trace_info()`'s cost before deleting the command |
| `Variable.trace_info()` | O(t²) | O(t) | Tcl restarts its walk of the trace list for each trace it reports; t is rarely more than one |
| `Variable.trace_variable(mode, callback)` / `Variable.trace()` / `Variable.trace_vdelete(mode, cbname)` / `Variable.trace_vinfo()` | O(t² + c) | O(t) | The same three operations through Tcl's old `trace variable` interface; deprecated in Python 3.14, and Tcl 9 dropped the interface, so under it they raise TclError |
| `del` a variable | O(c + t·f) | O(1) | Unsets the Tcl variable, firing its unset traces, and deletes the trace commands it registered, so a variable a widget still uses must be kept alive by the caller |

### Widgets

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Widget(master, **k)` / `BaseWidget(master, widgetName, cnf, kw)` / `Frame()` / `Label()` / `Message()` / `Menubutton()` / `LabelFrame()` / `Button()` / `Checkbutton()` / `Radiobutton()` / `Scale()` / `Scrollbar()` / `Entry()` / `Spinbox()` / `Listbox()` / `Menu()` / `Canvas()` / `Text()` / `PanedWindow()` | O(k² + p + t·f) | O(k + p) | One Tk window; the default name is the class name with a per-master counter, `!frame`, `!frame2`, appended to the master's path, a name already in the master's children destroys the old widget first at that widget's `destroy()` cost, and a `variable` or `textvariable` is read at once, firing its traces |
| `Toplevel(master, **k)` | O(k²) | O(k) | Also copies the root's title and icon name and registers the `WM_DELETE_WINDOW` protocol |
| `BaseWidget.destroy()` | O(d + c + n) | O(d) | Recurses through every descendant, holding a copy of each children list, then destroys the window, freeing its n items, entries or lines, and deletes every command registered on the subtree |
| `Button.invoke()` / `Checkbutton.invoke()` / `Radiobutton.invoke()` | O(f + t·f) | O(1) | Runs the command as a click would; the two with a variable write it first, firing its traces |
| `Button.flash()` / `Checkbutton.flash()` / `Radiobutton.flash()` | O(1) | O(1) | Blocks the caller while Tk redraws the button four times with a fixed delay between them |
| `Checkbutton.select()` / `Checkbutton.deselect()` / `Checkbutton.toggle()` / `Radiobutton.select()` / `Radiobutton.deselect()` | O(t·f) | O(1) | Set the widget's variable, which fires its write traces |
| `Scale.get()` / `Scale.coords(value)` / `Scale.identify(x, y)` | O(1) | O(1) | |
| `Scale.set(value)` | O(t·f) | O(1) | Writes the linked variable, firing its traces |
| `Scrollbar.get()` / `Scrollbar.set(first, last)` / `Scrollbar.activate()` / `Scrollbar.delta(dx, dy)` / `Scrollbar.fraction(x, y)` / `Scrollbar.identify(x, y)` | O(1) | O(1) | `set()` is what a scrolled widget calls on every view change, so it is the one to keep cheap |
| `OptionMenu(master, variable, value, *values, command)` | O(n²) | O(n) | A menubutton plus a menu built by one `add_command()` per value, each copying the entry array and registering a command; `name=` is accepted from Python 3.14 |
| `OptionMenu.destroy()` | O(d + c) | O(1) | The menu is a child, so the widget row covers it |

### Entry and Spinbox

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Entry.get()` / `Spinbox.get()` | O(m) | O(m) | The whole string |
| `Entry.insert(index, string)` / `Spinbox.insert()` / `Entry.delete(first, last)` / `Spinbox.delete()` | O(n + m + f + t·f) | O(n + m) | Tk keeps the text as one array and rebuilds it, then runs the `validatecommand` if one is set and writes a linked `textvariable`, firing its traces |
| `Entry.index(index)` / `Entry.icursor(index)` / `Spinbox.index()` / `Spinbox.icursor()` / `Spinbox.bbox(index)` / `Spinbox.identify(x, y)` | O(1) | O(1) | A numeric index; `@x` and `insert` resolve against the display layout |
| `Entry.selection_range(start, end)` / `Entry.selection_from()` / `Entry.selection_to()` / `Entry.selection_adjust()` / `Entry.selection_clear()` / `Entry.selection_present()` / `Spinbox.selection()` / `Spinbox.selection_range()` / `Spinbox.selection_from()` / `Spinbox.selection_to()` / `Spinbox.selection_adjust()` / `Spinbox.selection_clear()` / `Spinbox.selection_present()` / `Spinbox.selection_element()` | O(1) | O(1) | Also spelled `select_*`; `selection_present()` returns a bool |
| `Entry.scan_mark(x)` / `Entry.scan_dragto(x)` / `Spinbox.scan(*args)` / `Spinbox.scan_mark()` / `Spinbox.scan_dragto()` | O(1) | O(1) | |
| `Spinbox.invoke(element)` | O(n + m + f + t·f) | O(n + m) | Presses the up or down button: the text is rebuilt with the next value, validated, written to a linked `textvariable`, and `command` runs |

### Listbox

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Listbox.insert(END, *elements)` | O(m) | O(m) | Appends to the Tcl list Tk keeps, amortized; with a `listvariable` the list is shared and copied first, O(n + m) |
| `Listbox.insert(index, *elements)` / `Listbox.delete(first, last)` | O(n + m) | O(n) | Shifts the entries after the index and renumbers the selection and per-item option tables |
| `Listbox.index(index)` / `Listbox.size()` | O(1) | O(1) | |
| `Listbox.get(index)` / `Listbox.get(first, last)` | O(m) | O(m) | The entry's m characters, or a tuple of the m entries in the range |
| `Listbox.curselection()` | O(n) | O(s) | Scans every entry against the selection table |
| `Listbox.selection_set(first, last)` / `Listbox.selection_clear(first, last)` | O(m) | O(m) | One table entry per index in the range |
| `Listbox.selection_includes(index)` / `Listbox.selection_anchor(index)` / `Listbox.activate(index)` / `Listbox.see(index)` / `Listbox.nearest(y)` / `Listbox.bbox(index)` | O(1) | O(1) | Every line has the same height, so `nearest()` is arithmetic; `bbox()` is None off screen |
| `Listbox.itemcget(index, option)` / `Listbox.itemconfigure(index, **k)` | O(k²) | O(k) | Per-item colours live in a table keyed by index, so an item with none costs nothing |
| `Listbox.scan_mark(x, y)` / `Listbox.scan_dragto(x, y)` | O(1) | O(1) | |

### Menu

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Menu.add_command(**k)` / `Menu.add_cascade()` / `Menu.add_checkbutton()` / `Menu.add_radiobutton()` / `Menu.add_separator()` / `Menu.add(itemType, **k)` | O(n + k²) | O(n) | Tk reallocates the entry array on every add, so building a menu of n entries is O(n²); a `command` registers one Tcl command |
| `Menu.insert_command(index, **k)` / `Menu.insert_cascade()` / `Menu.insert_checkbutton()` / `Menu.insert_radiobutton()` / `Menu.insert_separator()` / `Menu.insert(index, itemType, **k)` | O(n + k²) | O(n) | The same reallocation, with the entries after the index shifted |
| `Menu.delete(index1, index2)` | O(m·(o + c) + n) | O(o) | Fetches every option of each of the m entries to find its command, deletes the command, then shifts the array |
| `Menu.index(index)` | O(n) | O(1) | An integer or `end` is O(1); a label is matched against every entry, and every other entry method that takes an index accepts a label at the same cost |
| `Menu.entrycget(index, option)` / `Menu.entryconfigure(index, **k)` | O(k²) | O(k) | The query with no options returns all o of them |
| `Menu.invoke(index)` | O(f + t·f) | O(1) | A checkbutton or radiobutton entry writes its variable first, firing its traces |
| `Menu.post(x, y)` / `Menu.tk_popup(x, y, entry)` | O(f) | O(1) | Run the `postcommand` first |
| `Menu.unpost()` / `Menu.activate(index)` / `Menu.type(index)` / `Menu.xposition(index)` / `Menu.yposition(index)` | O(1) | O(1) | |

### Canvas

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Canvas.create_line(*coords, **k)` / `Canvas.create_rectangle()` / `Canvas.create_oval()` / `Canvas.create_arc()` / `Canvas.create_polygon()` / `Canvas.create_text()` / `Canvas.create_image()` / `Canvas.create_bitmap()` / `Canvas.create_window()` | O(m + k²) | O(m + k) | m coordinates, or characters of a text item; the item is appended to the display list and entered in the id table, so item count does not matter |
| `Canvas.find_withtag(id)` / `Canvas.bbox(id)` / `Canvas.type(id)` | O(1) | O(1) | An integer id is one hash lookup |
| `Canvas.coords(id)` / `Canvas.gettags(id)` / `Canvas.itemcget(id, option)` | O(m) | O(m) | The item's m coordinates, tags or characters of the option's value, after the same lookup |
| `Canvas.find_withtag(tag)` / `Canvas.find_all()` / `Canvas.find_enclosed(x1, y1, x2, y2)` / `Canvas.find_overlapping()` / `Canvas.find_closest(x, y, halo, start)` / `Canvas.find_above(tagOrId)` / `Canvas.find_below(tagOrId)` / `Canvas.find(*args)` | O(n + m) | O(m) | A tag or a search walks the display list, testing every item, the geometric searches against each item's m coordinates; there is no spatial index |
| `Canvas.itemconfigure(tag, **k)` / `Canvas.move(tag, dx, dy)` / `Canvas.moveto(tag, x, y)` / `Canvas.scale(tag, x, y, xs, ys)` / `Canvas.delete(tag)` / `Canvas.dtag(tag, tagToDelete)` / `Canvas.tag_raise(tag)` / `Canvas.tag_lower(tag)` / `Canvas.bbox(*tags)` | O(n + m + k²) | O(k) | Every item matching the tag, found by the same walk, is updated, m coordinates in all; by id the walk is one hash lookup |
| `Canvas.coords(tagOrId, *xy)` | O(n + m) | O(m) | Sets the m coordinates of the first item matching a tag, or of the item by id without the walk |
| `Canvas.addtag(newtag, *args)` / `Canvas.addtag_withtag()` / `Canvas.addtag_all()` / `Canvas.addtag_enclosed()` / `Canvas.addtag_overlapping()` / `Canvas.addtag_closest()` / `Canvas.addtag_above()` / `Canvas.addtag_below()` | O(n + m) | O(m) | The same searches, adding the tag to each of the m matches |
| `Canvas.tag_bind(tag, sequence, func, add)` | O(b) | O(b) | One command per bound function, on the tag, not per item; `add` copies the script as `bind()` does |
| `Canvas.canvasx(screenx)` / `Canvas.canvasy(screeny)` / `Canvas.scan_mark(x, y)` / `Canvas.scan_dragto(x, y)` | O(1) | O(1) | |
| `Canvas.focus(id)` / `Canvas.icursor(id, index)` / `Canvas.index(id, index)` / `Canvas.insert(id, index, string)` / `Canvas.dchars(id, first, last)` / `Canvas.select_from(id, index)` / `Canvas.select_to()` / `Canvas.select_adjust()` / `Canvas.select_clear()` / `Canvas.select_item()` | O(m) | O(m) | Text-item editing, m characters of the item; by tag, `insert()` and `dchars()` edit every matching item after the O(n) walk, the others the first |
| `Canvas.postscript(**k)` | O(n + m) | O(m) | Renders every item, m coordinates and characters between them, into the output |

### Text

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Text.index(index)` / `Text.compare(index1, op, index2)` / `Text.mark_set(name, index)` / `Text.see(index)` | O(log L + m) | O(1) | Lines live in a B-tree; m is the characters before a `line.char` index on its line, walked to find it |
| `Text.get(index1, index2)` | O(log L + m) | O(m) | The range's m characters, after resolving each index as in the row above |
| `Text.insert(index, chars, *tags)` / `Text.delete(index1, index2)` / `Text.replace(index1, index2, chars)` | O(log L + m + ℓ) | O(m + ℓ) | Tk keeps each line's text in runs it splits and merges around the edit, copying the ℓ characters of the line; `insert()` with tags also adds each tag over the new text |
| `Text.count(index1, index2, *options)` | O(log L + m) | O(1) | `lines` and `indices` come from the tree's counts, `chars` and `displaychars` walk the range; `return_ints=True` is Python 3.13+, where a single option also returns a plain int |
| `Text.search(pattern, index, stopindex, **k)` | O(m) | O(ℓ) | An exact search scans the m characters between the indices, a line at a time through a buffer of that line; `regexp=True` matches the pattern against each line at the pattern's own cost instead |
| `Text.bbox(index)` / `Text.dlineinfo(index)` | O(log L + m) | O(1) | One index resolution; None when the index is off screen |
| `Text.mark_unset(*names)` / `Text.mark_gravity(name, direction)` / `Text.mark_next(index)` / `Text.mark_previous(index)` / `Text.mark_names()` | O(marks) | O(marks) | Marks are segments in the line they sit on; `mark_names()` lists all of them |
| `Text.tag_add(tag, index1, index2)` / `Text.tag_remove(tag, index1, index2)` | O(log L + m) | O(1) | Inserts toggle segments at the ends of the range and updates the tag counts up the tree |
| `Text.tag_ranges(tag)` / `Text.tag_nextrange(tag, index1, index2)` / `Text.tag_prevrange()` / `Text.tag_names(index)` | O(log L + m) | O(m) | Walk the toggles of the tag, m of them in the range; `tag_names()` with no index lists every tag |
| `Text.tag_configure(tag, **k)` / `Text.tag_cget(tag, option)` | O(k²) | O(k) | Per tag, not per character |
| `Text.tag_bind(tag, sequence, func, add)` | O(b) | O(b) | One command per bound function, on the tag; `add` copies the script as `bind()` does |
| `Text.tag_raise(tag, aboveThis)` / `Text.tag_lower(tag, belowThis)` | O(tags) | O(1) | Renumbers the priorities of the tags in between |
| `Text.tag_delete(*tags)` | O(L + m) | O(1) | Removes each tag's m toggles from the whole text |
| `Text.image_create(index, **k)` / `Text.window_create(index, **k)` | O(log L + m + k²) | O(k) | One embedded segment at the resolved index; `window_create()` with a `create` callback runs it at first display |
| `Text.image_configure(index, **k)` / `Text.image_cget(index, option)` / `Text.window_configure(index, **k)` / `Text.window_cget(index, option)` | O(log L + m + k²) | O(k) | |
| `Text.image_names()` / `Text.window_names()` / `Text.peer_names()` | O(m) | O(m) | |
| `Text.peer_create(newPathName, **k)` | O(k²) | O(k) | A second widget over the same B-tree, so its edits are the same edits |
| `Text.edit_undo()` / `Text.edit_redo()` | O(r·(log L + ℓ) + m) | O(m + ℓ) | Replays the r edits since the last separator, m characters in all, each as an edit of the line it touches; raises TclError when the stack is empty |
| `Text.edit_reset()` / `Text.edit_separator()` / `Text.edit_modified(arg)` / `Text.edit(*args)` | O(u) | O(1) | `edit_reset()` discards the u undo entries; the others are O(1) |
| `Text.dump(index1, index2, command, **k)` | O(m·f + c) | O(m) | One Tcl callback per item in the range, through a command registered for the call and deleted after it, collected into a list of triples unless `command` is given |
| `Text.debug(boolean)` / `Text.yview_pickplace(*what)` / `Text.scan_mark(x, y)` / `Text.scan_dragto(x, y)` | O(1) | O(1) | With `debug` on, every edit also checks the whole tree |

### XView and YView

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `XView.xview()` / `XView.xview_moveto(fraction)` / `XView.xview_scroll(number, what)` / `YView.yview()` / `YView.yview_moveto(fraction)` / `YView.yview_scroll(number, what)` | O(log L + m) | O(1) | The query returns the two visible fractions; for every widget but `Text` all six are O(1), while a `Text` finds the fraction's line through its pixel-height tree and walks the m lines a scroll passes |

### PanedWindow

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `PanedWindow.add(child, **k)` / `PanedWindow.remove(child)` / `PanedWindow.forget()` | O(n + k²) | O(n) | Tk rebuilds its pane array |
| `PanedWindow.panes()` | O(n) | O(n) | |
| `PanedWindow.paneconfigure(child, **k)` / `PanedWindow.panecget(child, option)` | O(n + k²) | O(k) | The child is found by scanning the panes |
| `PanedWindow.identify(x, y)` | O(n) | O(1) | |
| `PanedWindow.sash(*args)` / `PanedWindow.sash_coord(index)` / `PanedWindow.sash_mark(index, x, y)` / `PanedWindow.sash_place(index, x, y)` / `PanedWindow.proxy(*args)` / `PanedWindow.proxy_coord()` / `PanedWindow.proxy_forget()` / `PanedWindow.proxy_place(x, y)` | O(1) | O(1) | `sash_place()` moves every pane after the sash at the next idle layout |

### Image, PhotoImage and BitmapImage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Image(imgtype, name, cnf, master, **k)` | O(k²) | O(k) | Names default to `pyimage<n>` from a class counter; the same quadratic option marshalling as widgets |
| `PhotoImage(file=path)` / `PhotoImage(data=bytes)` / `BitmapImage(file=path)` | O(P) | O(P) | Decodes the whole image of P pixels into Tk's 32-bit buffer, whatever the file's depth, or the bitmap into one bit per pixel |
| `Image.configure(**k)` / `Image.__setitem__` / `Image.__getitem__` / `PhotoImage.cget(option)` | O(k²) | O(k) | `file=` or `data=` reloads the image, O(P) |
| `Image.height()` / `Image.width()` / `Image.type()` / `PhotoImage.get(x, y)` / `PhotoImage.transparency_get(x, y)` / `PhotoImage.transparency_set(x, y, boolean)` | O(1) | O(1) | |
| `PhotoImage.blank()` | O(P) | O(1) | Clears every pixel to transparent |
| `PhotoImage.copy(from_coords, zoom, subsample)` / `PhotoImage.zoom(x, y)` / `PhotoImage.subsample(x, y)` / `PhotoImage.copy_replace(source, **k)` | O(P) | O(P) | P is the destination's pixel count; the first three create a new image, `copy_replace()` and the keyword arguments are Python 3.13+ |
| `PhotoImage.put(data, to)` | O(m + P) | O(P) | m pixels given as rows of colour names; a region outside the image grows it to P pixels |
| `PhotoImage.read(filename, format, **k)` / `PhotoImage.write(filename, format, from_coords)` | O(P) | O(P) | `read()`, and `write()`'s `background` and `grayscale`, are Python 3.13+ |
| `PhotoImage.data(format, from_coords, **k)` | O(P) | O(P) | Python 3.13+; the image encoded, a tuple of row strings for the default format |
| `del` an image | O(m) | O(1) | Deletes the Tk image and tells each of the m widgets and canvas items showing it, which go blank, so keep a reference |

### Event, EventType and CallWrapper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Event.serial` / `Event.num` / `Event.focus` / `Event.height` / `Event.width` / `Event.keycode` / `Event.state` / `Event.time` / `Event.x` / `Event.y` / `Event.x_root` / `Event.y_root` / `Event.char` / `Event.send_event` / `Event.keysym` / `Event.keysym_num` / `Event.type` / `Event.widget` / `Event.delta` | O(1) | O(1) | Filled in once per delivered event from Tk's substitutions whether or not the handler reads them, except `focus` and `send_event`, which are left unset when Tk supplies no boolean; `widget` is looked up by path name, O(p), and `type` is an `EventType` |
| `EventType` | O(1) | O(1) | A `str` enum of the numeric event type codes |
| `CallWrapper(func, subst, widget)` | O(f) | O(1) | What every registered command runs: `subst` then `func`, with any exception but SystemExit sent to `report_callback_exception()` rather than raised |

### tkinter.ttk

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ttk.Widget(master, widgetname, **k)` / `ttk.Frame()` / `ttk.Label()` / `ttk.Labelframe()` / `ttk.LabelFrame()` / `ttk.Menubutton()` / `ttk.Button()` / `ttk.Checkbutton()` / `ttk.Radiobutton()` / `ttk.Entry()` / `ttk.Combobox()` / `ttk.Spinbox()` / `ttk.Scale()` / `ttk.Scrollbar()` / `ttk.Separator()` / `ttk.Sizegrip()` / `ttk.Progressbar()` / `ttk.Notebook()` / `ttk.Panedwindow()` / `ttk.PanedWindow()` / `ttk.Treeview()` | O(k² + t·f) | O(k) | The classic widget constructor and its option marshalling; only the style and item methods below format options linearly |
| `ttk.setup_master(master)` | O(1) | O(1) | The master given, or the default root |
| `ttk.tclobjs_to_py(adict)` | O(m) | O(m) | Converts the dict's values in place, a list per tuple value, m elements in all, and returns the same dict |
| `ttk.Widget.state(statespec)` / `ttk.Widget.instate(statespec, callback)` / `ttk.Widget.identify(x, y)` | O(m + f) | O(m) | m state flags; `instate` runs the callback only when they all hold |
| `ttk.Button.invoke()` / `ttk.Checkbutton.invoke()` / `ttk.Radiobutton.invoke()` | O(f + t·f) | O(1) | The two with a variable write it first, firing its traces |
| `ttk.Entry.bbox(index)` / `ttk.Entry.identify(x, y)` / `ttk.Scale.get(x, y)` | O(1) | O(1) | |
| `ttk.Combobox.set(value)` / `ttk.Spinbox.set(value)` | O(m + t·f) | O(m) | The value's m characters, copied in, and the traces of a linked `textvariable` |
| `ttk.Entry.validate()` | O(f) | O(1) | Runs the validation command |
| `ttk.Combobox.current(newindex)` | O(n) | O(1) | The query scans the values for the current one |
| `ttk.Scale.configure(**k)` | O(k² + b·f) | O(k) | The classic `configure()`, then generates `<<RangeChanged>>` when `from_` or `to` is among the options, running its handlers, the `LabeledScale` label's among them, before returning |
| `ttk.LabeledScale(master, variable, from_, to)` / `ttk.LabeledScale.value` | O(t·f) | O(1) | A frame, a scale, a label and one write trace on the variable; `value` reads or writes that variable, firing its traces |
| `ttk.LabeledScale.destroy()` | O(t² + c + d) | O(t) | Removes its trace at `trace_remove()`'s cost, then destroys the three widgets |
| `ttk.OptionMenu(master, variable, default, *values)` / `ttk.OptionMenu.set_menu(default, *values)` / `ttk.OptionMenu.destroy()` | O(n²) | O(n) | `set_menu()` deletes every entry and adds one radiobutton per value to a classic `Menu`, each add copying its entry array; `name=` is accepted from Python 3.14 |
| `ttk.Notebook.add(child, **k)` / `ttk.Notebook.insert(pos, child, **k)` / `ttk.Notebook.forget(tab_id)` / `ttk.Notebook.hide(tab_id)` / `ttk.Notebook.index(tab_id)` / `ttk.Notebook.select(tab_id)` / `ttk.Notebook.tab(tab_id, **k)` / `ttk.Notebook.identify(x, y)` | O(n + k) | O(k) | Tabs are an array Tk searches and shifts |
| `ttk.Notebook.tabs()` / `ttk.Notebook.enable_traversal()` | O(n) | O(n) | `enable_traversal()` binds the keyboard shortcuts on the toplevel once |
| `ttk.Panedwindow.insert(pos, child, **k)` / `ttk.Panedwindow.forget(pane)` / `ttk.Panedwindow.pane(pane, **k)` / `ttk.Panedwindow.sashpos(index, newpos)` | O(n + k) | O(k) | |
| `ttk.Progressbar.step(amount)` | O(t·f) | O(1) | Writes the linked variable, firing its traces |
| `ttk.Progressbar.start(interval)` / `ttk.Progressbar.stop()` | O(pending) | O(1) | `start()` schedules a repeating Tcl timer that steps the bar, and `stop()` cancels it, at the timer list's cost |
| `ttk.Style(master)` | O(1) | O(1) | |
| `ttk.Style.lookup(style, option, state, default)` | O(m) | O(1) | Scans the option's m state specifications from `map()` for the first that matches |
| `ttk.Style.theme_names()` | O(themes) | O(themes) | |
| `ttk.Style.configure(style, **k)` / `ttk.Style.map(style, **k)` / `ttk.Style.element_options(elementname)` / `ttk.Style.element_names()` | O(m) | O(m) | m is the total size of the options and their values, `map()`'s state specs included, formatted one by one; the query with no options returns all of them |
| `ttk.Style.layout(style, layoutspec)` / `ttk.Style.element_create(elementname, etype, *args, **k)` / `ttk.Style.theme_create(themename, parent, settings)` / `ttk.Style.theme_settings(themename, settings)` | O(m·depth) | O(m) | m is the size of the Tcl script the spec is formatted into, which indents each nesting level of a layout, and each level's script is copied again into its parent's; `vsapi` elements are Python 3.13+ |
| `ttk.Style.theme_use(themename)` | O(W) | O(1) | Switching themes restyles every ttk widget |
| `ttk.Treeview.insert(parent, index, iid, **k)` | O(i + m) | O(m) | Children are a linked list, walked i positions; `END` starts from a cached last child, so filling a level in order is linear, and only the first `END` after inserting elsewhere walks all n siblings. m is the size of the options and their values, and the item id is one hash entry |
| `ttk.Treeview.exists(item)` / `ttk.Treeview.parent(item)` / `ttk.Treeview.next(item)` / `ttk.Treeview.prev(item)` / `ttk.Treeview.focus(item)` | O(1) | O(1) | |
| `ttk.Treeview.item(item, option, **k)` / `ttk.Treeview.set(item, column, value)` / `ttk.Treeview.column(column, option, **k)` / `ttk.Treeview.heading(column, option, **k)` / `ttk.Treeview.tag_configure(tagname, option, **k)` | O(m) | O(m) | m is the total size of the options and their values, a `values` list included; the query with no option returns all of them, converted from Tcl objects |
| `ttk.Treeview.index(item)` / `ttk.Treeview.move(item, parent, index)` / `ttk.Treeview.reattach()` | O(i + depth) | O(1) | Walk the siblings to or from the position; `move()` first walks the new parent's item ancestors to refuse a cycle |
| `ttk.Treeview.get_children(item)` | O(n) | O(n) | n is that item's children |
| `ttk.Treeview.set_children(item, *newchildren)` | O(n·depth) | O(n) | Checks each new child against the item's ancestors to refuse a cycle, then relinks them |
| `ttk.Treeview.delete(*items)` / `ttk.Treeview.detach(*items)` | O(m + d) | O(m + depth) | `delete()` frees every descendant too, recursing down the item tree |
| `ttk.Treeview.selection()` / `ttk.Treeview.selection_set(*items)` / `ttk.Treeview.selection_add()` / `ttk.Treeview.selection_remove()` / `ttk.Treeview.selection_toggle()` | O(n) | O(s) | The query and `selection_set()` walk every item in the tree; `add`, `remove` and `toggle` touch only the m given |
| `ttk.Treeview.tag_has(tagname, item)` | O(n) | O(m) | With an item, one check; without, walks every item and returns the m carrying the tag |
| `ttk.Treeview.identify(component, x, y)` / `ttk.Treeview.identify_row(y)` / `ttk.Treeview.identify_column(x)` / `ttk.Treeview.identify_region(x, y)` / `ttk.Treeview.identify_element(x, y)` / `ttk.Treeview.see(item)` / `ttk.Treeview.bbox(item, column)` | O(n) | O(1) | A row is found by walking the displayed items from the top; `see()` opens every ancestor |
| `ttk.Treeview.tag_bind(tagname, sequence, callback)` | O(1) | O(1) | One command per bound function |

### tkinter.font

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `font.Font(root, font, name, exists, **k)` | O(k) | O(1) | One named Tk font, `font<n>` from a class counter; `font=` copies the actual attributes of an existing font first, `exists=True` checks the name against every named font, O(fonts) |
| `font.Font.actual(option)` / `font.Font.config(**k)` / `font.Font.configure()` / `font.Font.metrics(*options)` | O(o) | O(o) | `actual()` and `metrics()` with no arguments return every attribute, which forces the font to be loaded from the system the first time |
| `font.Font.cget(option)` / `font.Font.__getitem__` / `font.Font.__setitem__` | O(1) | O(1) | |
| `font.Font.measure(text)` | O(m) | O(1) | Lays out the m characters |
| `font.Font.copy()` | O(o) | O(o) | A new named font from `actual()` |
| `font.families()` / `font.names()` | O(m) | O(m) | Every family the display offers, or every named font in the interpreter |
| `font.nametofont(name, root)` | O(fonts) | O(fonts) | Wraps an existing named font without copying it, after checking the name against every named font |
| `del` a font | O(1) | O(1) | Deletes the named font if this object created it; Tk keeps the font alive while widgets still use it, the name is just gone for new ones |

### Dialogs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `commondialog.Dialog(master, **options)` | O(k) | O(k) | Stores the options; nothing is shown |
| `commondialog.Dialog.show(**options)` | O(w + k²) | O(1) | Runs the platform dialog and blocks until it closes; without a master, creates a withdrawn temporary root and destroys it afterwards |
| `messagebox.showinfo(title, message)` / `messagebox.showwarning()` / `messagebox.showerror()` / `messagebox.askquestion()` / `messagebox.askokcancel()` / `messagebox.askyesno()` / `messagebox.askyesnocancel()` / `messagebox.askretrycancel()` / `messagebox.Message` | O(w) | O(1) | `Message.show()` under a fixed icon and button set; the `ask*` functions but `askquestion()` convert the answer to a bool or None |
| `filedialog.askopenfilename(**options)` / `filedialog.asksaveasfilename()` / `filedialog.askopenfilenames()` / `filedialog.askdirectory()` / `filedialog.Open` / `filedialog.SaveAs` / `filedialog.Directory` | O(w) | O(m) | The native dialog lists directories itself; `askopenfilenames()` returns the m chosen names |
| `filedialog.askopenfile(mode, **options)` / `filedialog.askopenfiles()` / `filedialog.asksaveasfile()` | O(w) | O(m) | The same, then `open()` on each name |
| `filedialog.FileDialog(master, title)` / `filedialog.LoadFileDialog()` / `filedialog.SaveFileDialog()` | O(1) | O(1) | The pure-Tk dialog: a toplevel with two listboxes, two entries and three buttons |
| `filedialog.FileDialog.go(dir_or_file, pattern, default, key)` | O(w + E log E) | O(E) | Runs `filter_command()`, then `mainloop()` until a button ends it; `key=` remembers the directory and pattern per key in a module dict |
| `filedialog.FileDialog.filter_command(event)` | O(E log E) | O(E) | Lists the directory, sorts its E names, stats each one to split directories from files, and refills both listboxes |
| `filedialog.FileDialog.set_filter(dir, pat)` / `filedialog.FileDialog.get_filter()` / `filedialog.FileDialog.get_selection()` / `filedialog.FileDialog.set_selection(file)` / `filedialog.FileDialog.ok_event()` / `filedialog.FileDialog.ok_command()` / `filedialog.FileDialog.cancel_command()` / `filedialog.FileDialog.quit(how)` / `filedialog.FileDialog.dirs_select_event()` / `filedialog.FileDialog.files_double_event()` / `filedialog.FileDialog.files_select_event()` | O(1) | O(1) | `ok_command()` ends the dialog with the selection |
| `filedialog.FileDialog.dirs_double_event(event)` | O(E log E) | O(E) | Enters the directory through `filter_command()` |
| `filedialog.LoadFileDialog.ok_command()` / `filedialog.SaveFileDialog.ok_command()` | O(w) | O(1) | One or two `stat` calls, and a bell instead of ending the dialog for a missing file or a directory; the save variant asks for confirmation before overwriting, blocking until answered |
| `simpledialog.Dialog(parent, title)` / `simpledialog.Dialog.result` | O(w) | O(1) | Builds `body()` and `buttonbox()`, grabs, and does not return from the constructor until the dialog is closed; `result` holds what `apply()` stored |
| `simpledialog.Dialog.body(master)` / `simpledialog.Dialog.buttonbox()` / `simpledialog.Dialog.validate()` / `simpledialog.Dialog.apply()` / `simpledialog.Dialog.ok(event)` / `simpledialog.Dialog.cancel(event)` / `simpledialog.Dialog.destroy()` | O(f) | O(1) | Overridable hooks; `ok()` runs `validate()` then `apply()` |
| `simpledialog.SimpleDialog(master, text, buttons, default, cancel, title, class_)` | O(n²) | O(n) | One button per entry of `buttons`, each packed after the ones before it |
| `simpledialog.SimpleDialog.go()` | O(w) | O(1) | `mainloop()` until `done()`, then returns the button index |
| `simpledialog.SimpleDialog.return_event(event)` / `simpledialog.SimpleDialog.wm_delete_window()` / `simpledialog.SimpleDialog.done(num)` | O(1) | O(1) | |
| `simpledialog.askstring(title, prompt)` / `simpledialog.askinteger()` / `simpledialog.askfloat()` | O(w) | O(1) | A `Dialog` with an entry; the two numeric ones re-prompt on a value outside `minvalue` and `maxvalue` |
| `colorchooser.askcolor(color, **options)` / `colorchooser.Chooser` | O(w) | O(1) | Returns the `(r, g, b)` tuple and the hex string, or `(None, None)` |
| `dialog.Dialog(master, **options)` | O(w + k²) | O(1) | `tk_dialog` blocks in the constructor; `num` holds the button pressed |
| `dialog.Dialog.destroy()` | O(1) | O(1) | Nothing: the window is gone when the constructor returns |
| `scrolledtext.ScrolledText(master, **k)` / `scrolledtext.ScrolledText.frame` / `scrolledtext.ScrolledText.vbar` | O(k²) | O(1) | A `Text` in a `Frame` with a `Scrollbar`; the frame's geometry methods are copied onto the widget, so `pack()` and `grid()` manage `frame`, and `vbar` is the scrollbar |
| `dnd.dnd_start(source, event)` / `dnd.DndHandler(source, event)` | O(1) | O(1) | Binds motion and release on the widget under the pointer; None while a drag is already in progress on that root |
| `dnd.DndHandler.on_motion(event)` | O(p·f) | O(1) | Finds the widget under the pointer and walks up its path calling each `dnd_accept`, then the target's `dnd_enter`, `dnd_leave` or `dnd_motion` |
| `dnd.DndHandler.on_release(event)` / `dnd.DndHandler.cancel(event)` / `dnd.DndHandler.finish(event, commit)` | O(b + c + f) | O(b) | Unbind the two handlers, restore the cursor, and call the target's `dnd_commit` or `dnd_leave` and the source's `dnd_end` |

## Callbacks Are Not Free to Register

Each `command=`, `bind()` and `after()` creates a Tcl command and appends its name to the widget's registry; `trace_add()` does the same on the variable's own registry, which its `del` clears. A registry is a list, so cancelling a timer or deleting a command scans it, and the callback a timer runs deletes its own command when it fires. Bindings and options never delete theirs until the widget is destroyed, so rebinding the same sequence in a loop leaks a command per iteration; `unbind()` with the id `bind()` returned is what frees it.

```python
import tkinter as tk

root = tk.Tcl()  # no display needed for timers, variables and traces

fired = []
root.after(0, fired.append, "timer")  # O(1): registers one Tcl command
root.after_idle(fired.append, "idle")  # O(1)
cancelled = root.after(0, fired.append, "cancelled")
root.after_cancel(cancelled)  # O(c): finds and deletes the command
root.update()  # O(e·(f + c)): runs what is due; each callback deletes its command
print(fired)

counter = tk.IntVar(master=root, value=1)  # O(1): one Tcl variable
writes = []
name = counter.trace_add("write", lambda *args: writes.append(counter.get()))  # O(1)
counter.set(counter.get() + 1)  # O(m + t·f): the trace runs inside set()
counter.trace_remove("write", name)  # O(t² + c)
counter.set(10)
print(writes, counter.get())
```

Output:

```
['timer', 'idle']
[2] 10
```

## Find by Id, Not by Tag

A canvas keeps its items in a display list with a hash table from id to item. `find_withtag(3)` is one lookup; `find_withtag("dot")` walks every item, and so does every other search and every operation applied through a tag. Keep the ids `create_*` returns when the same items are moved every frame.

```python
import tkinter as tk

root = tk.Tk()
canvas = tk.Canvas(root, width=200, height=200)
canvas.pack()

ids = [
    canvas.create_oval(x, x, x + 5, x + 5, tags="dot")  # O(m + k²), m = 4 coordinates
    for x in range(0, 200, 10)
]

canvas.move(ids[0], 1, 1)  # O(m): one hash lookup, then its four coordinates
canvas.move("dot", 1, 1)  # O(n): every item is tested for the tag
print(len(canvas.find_withtag("dot")))  # O(n)
print(canvas.find_withtag(ids[0]) == (ids[0],))  # O(1)

root.destroy()
```

Output:

```
20
True
```

## Text Indices Are Logarithmic, Ranges Are Linear

A `Text` widget's lines are a B-tree, so resolving `"500.0"` costs O(log L) however long the document is, and so does `insert()` at that index apart from the characters inserted and the line they land on. What is linear is the range: `get("1.0", "end")` copies the whole document, `search()` scans it, and `tag_add()` over the whole document leaves the tag's toggles for `tag_ranges()` to walk. A `Listbox` is the opposite shape: an array, O(1) to index, O(n) to insert anywhere but the end.

```python
import tkinter as tk

root = tk.Tk()
text = tk.Text(root)
text.insert("end", "\n".join(f"line {i}" for i in range(1000)))  # O(log L + m)

print(text.index("500.0 lineend"))  # O(log L)
print(text.index("end"))  # O(log L): the line count comes from the tree
print(text.search("line 999", "1.0"))  # O(m): scans from the top

listbox = tk.Listbox(root)
listbox.insert("end", *range(1000))  # O(m), amortized
listbox.insert(0, "first")  # O(n + m): shifts every entry
print(listbox.size(), listbox.get(0), listbox.get(500))  # O(1) each

root.destroy()
```

Output:

```
500.8
1001.0
1000.0
1001 first 499
```

## Related Documentation

- [turtle Module](turtle.md) - draws on a `Canvas`, so every turtle step is an item update
- [curses Module](curses.md) - the terminal alternative
- [threading Module](threading.md) - Tk runs on one thread; hand results to it with `after()`
