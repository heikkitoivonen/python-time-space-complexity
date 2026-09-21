# sys Module Complexity

The `sys` module is the interpreter talking about itself: the module table, the import path, the
standard streams, the exception currently being handled, the tracing and auditing hooks, and a
long list of values fixed when the process started. Almost every name on it reads or writes one
field, which is why almost every row below is O(1).

The two big containers are not copies: `sys.modules` and `sys.path` are the interpreter's own
dict and list, so what you mutate is what the import system uses next. The rows worth knowing
are the handful that are not constant: walking the frame chain, visiting every live thread,
interning a string, running the audit hooks, and instrumenting code for `sys.monitoring`.

`d` is the frame depth a walk covers, `t` the live threads, `h` the installed audit hooks, `m`
the entries in `sys.modules`, `e` the entries in `sys.path`, `b` the entries in
`sys.builtin_module_names`, `f` the frames on all thread stacks at once, `c` the bytecode of one
code object, `C` the bytecode of all the distinct code objects on those stacks, `r` the
characters in a value's `repr`, and `i` the live interpreters. Dict and set bounds treat key
hashing as O(1).

## Complexity Reference

### Exception state and exit

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.exc_info()` | O(1) | O(1) | Builds a 3-tuple from the thread's current exception |
| `sys.exception()` | O(1) | O(1) | The exception itself, with no tuple built; Python 3.11+ |
| `sys.last_exc`, `sys.last_type`, `sys.last_value`, `sys.last_traceback` | O(1) | O(1) | Bound by the interpreter when it reports an unhandled exception, just before it calls `sys.excepthook` - so a replacement hook and anything running after it can read them, and calling the hook yourself does not bind them. Before that, reading one raises `AttributeError`. `last_exc` is Python 3.12+ |
| `sys.excepthook(type, value, traceback)`, `sys.__excepthook__` | O(d + s + m) | O(s + m) | Walks the whole traceback and reads the source line for each frame it prints; s = characters of source read, m = characters the exception itself renders to - its `str()` plus any `__notes__`. A repeated frame prints three times and then a count, and a chained exception adds its own frames |
| `sys.unraisablehook(unraisable)`, `sys.__unraisablehook__` | O(d + s + m) | O(s + m) | The same formatting for an exception that had nowhere to propagate, such as one raised in `__del__`; here m also covers the `repr()` of the object the report names |
| `sys.tracebacklimit` | O(1) | O(1) | Caps how many frames the two rows above print, not how many they walk; unbound by default, which means no cap |
| `sys.exit(code)` | O(1) | O(1) | Raises `SystemExit`, so this is the cost of the raise, not of the shutdown that follows |

### Frames and threads

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys._getframe(depth=0)` | O(d) | O(1) | Follows the frame chain one link at a time; `ValueError` past the bottom |
| `sys._getframemodulename(depth=0)` | O(d) | O(1) | The same walk, returning `__name__` from that frame's globals; Python 3.12+ |
| `sys._current_frames()` | O(t) | O(t) | One entry per live thread |
| `sys._current_exceptions()` | O(t) | O(t) | One entry per live thread as well: a thread handling nothing maps to `None` rather than being left out. Python 3.12+ stores the exception; earlier versions store an `exc_info()` triple |
| `sys.getrecursionlimit()` | O(1) | O(1) | Reads one interpreter field |
| `sys.setrecursionlimit(limit)` | O(t) | O(1) | Writes through to every thread state from Python 3.11; a limit below the current depth raises `RecursionError` |
| `sys.getswitchinterval()`, `sys.setswitchinterval(interval)` | O(1) | O(1) | One field each |

### Tracing, profiling and auditing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.settrace(function)`, `sys.setprofile(function)` | O(f + C) | O(C) | From Python 3.12 these run on the `sys.monitoring` machinery, so installing one pauses every thread and instruments the code objects on their stacks; on 3.10 and 3.11 it is O(1). Either way the bill that matters comes afterwards, one call per traced event |
| `sys.gettrace()`, `sys.getprofile()` | O(1) | O(1) | Reads the installed function back |
| `sys.call_tracing(func, args)` | O(1) plus `func` | O(1) | Saves and restores the tracing state around one call, so a trace function can re-enter itself; on Python 3.11 the call runs untraced instead |
| `sys.audit(event, *args)` | O(h) | O(1) | Hooks are called in the order they were added, until one of them raises - that exception propagates and the rest are skipped |
| `sys.addaudithook(hook)` | O(h) | O(1) | Raises the `sys.addaudithook` event first, so every hook already installed runs before the append; there is no matching remove |
| `sys.activate_stack_trampoline(backend)`, `sys.deactivate_stack_trampoline()` | O(1) | O(1) | Switches the perf profiler trampoline; Linux only, and `ValueError` where the build lacks the backend. Python 3.12+ |
| `sys.is_stack_trampoline_active()` | O(1) | O(1) | Reads one flag; Python 3.12+ |

### sys.monitoring

Python 3.12+. Six tool slots, each with its own callbacks and event mask.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.monitoring.use_tool_id(tool_id, name)` | O(1) | O(1) | Claims one of the ids 0 to 5; `ValueError` if it is already in use |
| `sys.monitoring.get_tool(tool_id)` | O(1) | O(1) | The registered name, or `None` |
| `sys.monitoring.register_callback(tool_id, event, func)` | O(1) | O(1) | Swaps one slot and hands back the previous callback |
| `sys.monitoring.set_events(tool_id, event_set)` | O(f + C) | O(C) | Pauses every thread, walks all their frames, and instruments the distinct code objects it finds; anything not currently executing is instrumented when it is next entered |
| `sys.monitoring.get_events(tool_id)` | O(1) | O(1) | One bitmask read |
| `sys.monitoring.set_local_events(tool_id, code, event_set)` | O(c) | O(c) | Instruments that one code object, c = its bytecode |
| `sys.monitoring.get_local_events(tool_id, code)` | O(1) | O(1) | One bitmask read |
| `sys.monitoring.restart_events()` | O(f + C) | O(C) | The same walk as `set_events`, so locations a callback turned off start firing again |
| `sys.monitoring.clear_tool_id(tool_id)` | O(f + C) | O(1) | Drops the tool's callbacks and clears its events, keeping the slot; Python 3.14+ |
| `sys.monitoring.free_tool_id(tool_id)` | O(f + C) | O(1) | From Python 3.14 it clears the events as above and then releases the slot. On 3.12 and 3.13 it releases the name and nothing else, at O(1) - the callbacks stay registered and instrumented code keeps calling them |
| `sys.monitoring.events`, `sys.monitoring.DISABLE`, `sys.monitoring.MISSING` | O(1) | O(1) | The event namespace, the value a callback returns to stop an event firing at that location, and the value handed to a callback for an argument the interpreter does not have |
| `sys.monitoring.DEBUGGER_ID`, `sys.monitoring.COVERAGE_ID`, `sys.monitoring.PROFILER_ID`, `sys.monitoring.OPTIMIZER_ID` | O(1) | O(1) | Conventional slot numbers |

### Objects and memory

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.getsizeof(object, default)` | O(1) | O(1) | Calls `object.__sizeof__()`, adding the GC header where the type has one; O(1) for builtin types, and whatever a custom `__sizeof__` costs otherwise. It never looks inside a container |
| `sys.getrefcount(object)` | O(1) | O(1) | Reads the refcount field |
| `sys.intern(string)` | O(len(s)) | O(1) | Hashes and looks the string up, and O(1) when it is already interned. The table holds no reference of its own, so keep the result alive or the entry goes with it - except on Python 3.12.0 to 3.12.6, where the string is immortal instead |
| `sys._is_interned(string)` | O(1) | O(1) | Reads a flag on the object instead of searching the table, so it does not pay the row above; Python 3.13+ |
| `sys._is_immortal(object)` | O(1) | O(1) | One refcount comparison; Python 3.14+ |
| `sys.getunicodeinternedsize()` | O(1) | O(1) | A stored count; Python 3.12+ |
| `sys.getallocatedblocks()` | O(i) | O(1) | Sums one counter per live interpreter, so O(1) in an ordinary single-interpreter program; from Python 3.13 it pauses every thread while it reads them |
| `sys._clear_type_cache()` | O(1) | O(1) | Walks a method cache of fixed size; deprecated from Python 3.13 |
| `sys._clear_internal_caches()` | O(x) | O(1) | The same clear, plus invalidating the x live tier-2 executors; Python 3.13+ |
| `sys._debugmallocstats()` | O(a) | O(1) | Writes a per-size-class summary to stderr; a = the allocator's arenas |
| `sys.get_int_max_str_digits()`, `sys.set_int_max_str_digits(maxdigits)` | O(1) | O(1) | One field; what it caps is the quadratic work in `int(str)` and `str(int)`. Python 3.10.7+ |
| `sys.getobjects(limit, type)` | O(objects) | O(limit) | Walks every tracked object; only exists in a `Py_TRACE_REFS` debug build |
| `sys.maxsize`, `sys.maxunicode` | O(1) | O(1) | Build-time constants |

### Modules and the import path

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.modules` | O(1) | O(1) | The import system's own dict, not a copy of it |
| `sys.modules[name]`, `name in sys.modules` | O(1) avg | O(1) | An ordinary dict, so O(m) in the worst case if every key collides |
| Iterating `sys.modules` | O(m) | O(1) | |
| `sys.path` | O(1) | O(1) | The list the path finder reads on every import miss |
| `sys.path.append(entry)` | O(1) amortized | O(1) | O(e) on the resize |
| `sys.path.insert(0, entry)` | O(e) | O(1) | Shifts every existing entry |
| `entry in sys.path` | O(e) | O(1) | Linear scan |
| `sys.meta_path` | O(1) | O(1) | List read; an import that misses costs one `find_spec()` per finder on it |
| `sys.path_hooks` | O(1) | O(1) | List read; tried in order for a `sys.path` entry that is not in the cache below |
| `sys.path_importer_cache` | O(1) avg | O(1) | Dict keyed by path entry, so the `sys.path_hooks` scan is paid once per entry |
| `sys.builtin_module_names` | O(1) | O(1) | A tuple, so `name in sys.builtin_module_names` is O(b) |
| `sys.stdlib_module_names` | O(1) | O(1) | A frozenset, so membership is O(1) average |
| `sys.dont_write_bytecode`, `sys.pycache_prefix` | O(1) | O(1) | Where compiled bytecode goes, and whether it is written at all |

### Standard streams and interactive hooks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.stdin`, `sys.stdout`, `sys.stderr` | O(1) | O(1) | Attribute reads, and rebinding one is an O(1) assignment; writing costs the text written |
| `sys.__stdin__`, `sys.__stdout__`, `sys.__stderr__` | O(1) | O(1) | The originals, kept so a replacement can be undone |
| `sys.displayhook(value)`, `sys.__displayhook__` | O(r) plus `__repr__` | O(r) | Writes `repr(value)` to `sys.stdout` and binds `builtins._` to the value; r is what `__repr__` returned, and producing it costs whatever the object charges. `None` returns immediately, writing nothing and leaving `builtins._` alone |
| `sys.breakpointhook(*args, **kwargs)`, `sys.__breakpointhook__` | O(1) plus the hook | O(1) | What `breakpoint()` calls; the default imports `pdb` on first use and then waits for input, and `PYTHONBREAKPOINT` names what runs instead |
| `sys.ps1`, `sys.ps2` | O(1) | O(1) | Bound only in interactive mode |
| `sys.__interactivehook__` | O(1) plus the hook | O(1) | Called once at interactive startup; `site` installs the one that loads readline history |

### Asynchronous generator and coroutine hooks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.get_asyncgen_hooks()` | O(1) | O(1) | Builds a two-field named tuple from the thread state |
| `sys.set_asyncgen_hooks(firstiter, finalizer)` | O(1) | O(1) | Per thread; `firstiter` runs once per asynchronous generator, not once per step of it |
| `sys.get_coroutine_origin_tracking_depth()` | O(1) | O(1) | One field |
| `sys.set_coroutine_origin_tracking_depth(depth)` | O(1) | O(1) | Constant to set, but while it is non-zero every coroutine created walks up to `depth` frames |

### Encodings and dynamic loading

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.getdefaultencoding()`, `sys.getfilesystemencoding()`, `sys.getfilesystemencodeerrors()` | O(1) | O(1) | Strings decided at startup and handed back |
| `sys.getdlopenflags()`, `sys.setdlopenflags(n)` | O(1) | O(1) | Unix only; the flags extension loading passes to `dlopen()` |

### Interpreter configuration

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.version_info`, `sys.version_info.major`, `sys.version_info.minor`, `sys.version_info.micro`, `sys.version_info.releaselevel`, `sys.version_info.serial` | O(1) | O(1) | A struct sequence; each field is an index read |
| `sys.implementation`, `sys.implementation.name`, `sys.implementation.version`, `sys.implementation.hexversion`, `sys.implementation.cache_tag`, `sys.implementation.supports_isolated_interpreters` | O(1) | O(1) | Fixed at startup; `supports_isolated_interpreters` is Python 3.14+ |
| `sys.flags` | O(1) | O(1) | The command-line and environment switches, fixed at startup - except `int_max_str_digits`, which `set_int_max_str_digits()` rewrites from Python 3.14 |
| `sys.flags.debug`, `sys.flags.inspect`, `sys.flags.interactive`, `sys.flags.optimize`, `sys.flags.dont_write_bytecode`, `sys.flags.no_user_site`, `sys.flags.no_site`, `sys.flags.ignore_environment`, `sys.flags.verbose`, `sys.flags.bytes_warning`, `sys.flags.quiet`, `sys.flags.hash_randomization`, `sys.flags.isolated`, `sys.flags.dev_mode`, `sys.flags.utf8_mode`, `sys.flags.warn_default_encoding`, `sys.flags.safe_path`, `sys.flags.int_max_str_digits`, `sys.flags.gil`, `sys.flags.thread_inherit_context`, `sys.flags.context_aware_warnings` | O(1) | O(1) | Index reads; `safe_path` is Python 3.11+, `gil` 3.13+, and `thread_inherit_context` and `context_aware_warnings` 3.14+ |
| `sys.float_info`, `sys.float_info.max`, `sys.float_info.max_exp`, `sys.float_info.max_10_exp`, `sys.float_info.min`, `sys.float_info.min_exp`, `sys.float_info.min_10_exp`, `sys.float_info.dig`, `sys.float_info.mant_dig`, `sys.float_info.epsilon`, `sys.float_info.radix`, `sys.float_info.rounds` | O(1) | O(1) | The C `float.h` limits, as index reads |
| `sys.int_info`, `sys.int_info.bits_per_digit`, `sys.int_info.sizeof_digit`, `sys.int_info.default_max_str_digits`, `sys.int_info.str_digits_check_threshold` | O(1) | O(1) | How `int` stores digits, and the limit described under `set_int_max_str_digits` |
| `sys.hash_info`, `sys.hash_info.width`, `sys.hash_info.modulus`, `sys.hash_info.inf`, `sys.hash_info.nan`, `sys.hash_info.imag`, `sys.hash_info.algorithm`, `sys.hash_info.hash_bits`, `sys.hash_info.seed_bits`, `sys.hash_info.cutoff` | O(1) | O(1) | The parameters of the hash the dict and set bounds assume is O(1) |
| `sys.thread_info`, `sys.thread_info.name`, `sys.thread_info.lock`, `sys.thread_info.version` | O(1) | O(1) | The threading implementation, fixed at build time |

### Runtime data attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.platform`, `sys.version`, `sys.hexversion`, `sys.api_version`, `sys.byteorder`, `sys.copyright`, `sys.float_repr_style`, `sys.abiflags` | O(1) | O(1) | Plain attribute reads, computed once at startup |
| `sys.executable`, `sys.prefix`, `sys.exec_prefix`, `sys.base_prefix`, `sys.base_exec_prefix`, `sys.platlibdir` | O(1) | O(1) | Paths resolved during startup |
| `sys.argv`, `sys.orig_argv` | O(1) | O(1) | Lists built once; `orig_argv` keeps the interpreter's own options, which `argv` drops. Python 3.10+ |
| `sys.warnoptions`, `sys._xoptions` | O(1) | O(1) | The `-W` and `-X` options as given on the command line |
| `sys.is_finalizing()`, `sys._is_gil_enabled()` | O(1) | O(1) | One flag each; `_is_gil_enabled` is Python 3.13+ |
| `sys._jit.is_available()`, `sys._jit.is_enabled()`, `sys._jit.is_active()` | O(1) | O(1) | Flag reads for the tier-2 JIT; Python 3.14+ |

### Platform-specific and remote debugging

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sys.getwindowsversion()` | O(1) | O(1) | Windows only |
| `sys.dllhandle`, `sys.winver` | O(1) | O(1) | Windows only |
| `sys._enablelegacywindowsfsencoding()` | O(1) | O(1) | Windows only; deprecated from Python 3.13 |
| `sys.getandroidapilevel()` | O(1) | O(1) | Android only |
| `sys._emscripten_info`, `sys._emscripten_info.emscripten_version`, `sys._emscripten_info.runtime`, `sys._emscripten_info.pthreads`, `sys._emscripten_info.shared_memory` | O(1) | O(1) | Emscripten only |
| `sys.remote_exec(pid, script)` | O(1) | O(1) | Checks the script is readable, then writes its path into the target process; the target compiles and runs it at its next safe point, so the script's own cost lands there. Python 3.14+ |
| `sys.is_remote_debug_enabled()` | O(1) | O(1) | Whether this interpreter will accept the row above; Python 3.14+ |

## Walking the Stack

`sys._getframe(depth)` follows one link per level, so asking for the caller is cheap and asking
for the frame 500 levels up is not. `sys._current_frames()` and `sys._current_exceptions()` cost
one entry per live thread instead, whatever each stack looks like.

```python
import sys

def innermost():
    # O(d) - two links up from here
    return sys._getframe(2).f_code.co_name

def middle():
    return innermost()

def outermost():
    return middle()

assert outermost() == 'outermost'

frames = sys._current_frames()          # O(t) - one entry per live thread
exceptions = sys._current_exceptions()  # O(t) - the same threads
assert set(exceptions) == set(frames)

try:
    sys._getframe(1_000_000)
except ValueError as error:
    assert 'call stack is not deep enough' in str(error)
else:
    raise AssertionError('the walk ran off the bottom without complaining')
```

## The Recursion Limit

Reading the limit is one field. Setting it has been a write through every thread state since
Python 3.11, which is what the O(t) in the table is.

```python
import sys

original = sys.getrecursionlimit()    # O(1)
sys.setrecursionlimit(original + 500)  # O(t) - one pass over the thread states
assert sys.getrecursionlimit() == original + 500

try:
    sys.setrecursionlimit(1)
except RecursionError as error:
    assert 'limit is too low' in str(error)
else:
    raise AssertionError('a limit below the current depth was accepted')
finally:
    sys.setrecursionlimit(original)
```

## Interning Strings

The first `sys.intern()` of a string hashes it and compares it against the table entry it lands
on, so it costs the string's length. Handing back a string that is already interned costs
nothing of the sort, and `sys._is_interned()` answers the question without the lookup at all.

```python
import sys

first = sys.intern(''.join(['inter', 'ning']))   # O(len(s)) - hashed and looked up
second = sys.intern(''.join(['inter', 'ning']))  # O(len(s)), then the table hit
assert first is second

assert sys.intern(first) is first                # O(1) - already interned

if sys.version_info >= (3, 13):
    assert sys._is_interned(first) is True                        # O(1) - a flag read
    assert sys._is_interned(''.join(['not', '-interned'])) is False
```

!!! warning "Interning is permanent on Python 3.12.0 to 3.12.6"
    Across those seven patch releases an interned string is immortal: dropping every reference to
    it does not give the memory back, so interning many distinct strings grows the process for
    good. 3.12.7 restored the mortal table every other supported release has.

## Tracing, Profiling and Monitoring

### Installing a Tracer, and Then Paying for It

`sys.settrace()` and `sys.setprofile()` store one function, and from Python 3.12 they also go
through the `sys.monitoring` machinery below, so installing one pauses every thread and
instruments the code objects on their stacks. Either way the bill that dominates comes
afterwards, once per traced event - for `settrace()`, once per line executed.

```python
import sys

def work(count):
    total = 0
    for value in range(count):
        total += value
    return total

lines = []

def tracer(frame, event, arg):
    if event == 'line':
        lines.append(frame.f_lineno)
    return tracer

original = sys.gettrace()   # O(1)
sys.settrace(tracer)        # O(f + C) from 3.12, O(1) before it
try:
    work(5)                 # one tracer call per line executed
finally:
    sys.settrace(original)  # O(f + C) from 3.12, O(1) before it

assert len(lines) > 5, lines
assert sys.gettrace() is original
```

### Instrumentation Follows the Code Object

A `sys.monitoring` callback still runs once per event, but the event is reached by instrumented
bytecode rather than by a per-frame trace function, so a tool can ask for one event in one code
object and pay nothing anywhere else. What switching it on costs is the code it rewrites:
`set_local_events()` instruments the one code object it is handed, and `set_events()` pauses the
interpreter and instruments everything currently on a stack, leaving the rest to be instrumented
as it is entered.

```python
import sys

if sys.version_info >= (3, 12):
    monitoring = sys.monitoring
    tool = monitoring.DEBUGGER_ID
    monitoring.use_tool_id(tool, 'page-example')  # O(1)

    seen = []
    monitoring.register_callback(                 # O(1)
        tool, monitoring.events.LINE, lambda code, lineno: seen.append(lineno)
    )

    def counted():
        total = 0
        for value in range(3):
            total += value
        return total

    # O(c) - instruments this one code object, c = its bytecode
    monitoring.set_local_events(tool, counted.__code__, monitoring.events.LINE)
    assert counted() == 3
    monitoring.set_local_events(tool, counted.__code__, 0)  # O(c)

    assert monitoring.get_tool(tool) == 'page-example'      # O(1)
    monitoring.free_tool_id(tool)                           # O(f + C) from 3.14
    assert len(seen) > 3, seen
```

## Auditing

A `sys.audit()` call runs the installed hooks in order until one of them raises, so the cost of
an event is the number of hooks times whatever each one does. Adding a hook costs the same walk,
because `addaudithook()` raises its own event first, and there is no way to undo it.

```python
import sys

events = []
sys.addaudithook(lambda event, args: events.append(event))  # O(h), and permanent
assert events == []             # the hook is installed after its own event is raised

sys.addaudithook(lambda event, args: None)   # O(h) - the hook above sees this one arrive
assert events == ['sys.addaudithook']

sys.audit('page.probe', 1, 2)   # O(h) - each hook in turn, until one raises
assert events[-1] == 'page.probe'

assert not hasattr(sys, 'removeaudithook')
```

## Modules and the Import Path

`sys.modules` is the import system's cache, and looking a name up in it is the dict lookup that
makes a repeated `import` cheap. The two module-name collections beside it are not
interchangeable: one is a tuple and one is a frozenset.

```python
import json
import sys

assert sys.modules['json'] is json      # O(1) average - the import cache itself
assert type(sys.modules) is dict

assert 'sys' in sys.builtin_module_names   # O(b) - a tuple, scanned linearly
assert 'json' in sys.stdlib_module_names   # O(1) average - a frozenset
```

`sys.path` is a list, so where you add an entry decides what it costs. Prepending k entries one
at a time shifts everything in front of each new one - O(k*e + k**2), since the list is longer
every time round. A slice assignment shifts each entry once, at O(e + k), and keeps the list
object the import system already holds.

```python
import sys

original = list(sys.path)
additions = ['/one', '/two', '/three']

for entry in additions:
    sys.path.insert(0, entry)    # the list grows as it goes, so the loop is O(k*e + k**2)
assert sys.path[:3] == ['/three', '/two', '/one']

sys.path[:] = original
identity = id(sys.path)
sys.path[:0] = additions         # O(e + k) once, and the same list object
assert id(sys.path) == identity
assert sys.path[:3] == additions

sys.path[:] = original
assert '/one' not in sys.path    # O(e) - a linear scan
```

## Replacing the Standard Streams

`sys.stdout` is a name like any other, so redirecting it is an assignment and restoring it is
another. What costs anything is the text that goes through the replacement.

```python
import builtins
import io
import sys

original = sys.stdout
captured = io.StringIO()

sys.stdout = captured            # O(1)
print('redirected')
sys.stdout = original            # O(1)
assert captured.getvalue() == 'redirected\n'

shown = io.StringIO()
sys.stdout = shown
sys.displayhook([1, 2, 3])       # O(r) - r = characters in repr(value)
sys.stdout = original
assert shown.getvalue() == '[1, 2, 3]\n'
assert builtins._ == [1, 2, 3]
```

## Sizing an Object

`sys.getsizeof()` asks the object and nobody else. A list of one large object is the same size
as a list of one small one, because what the list holds is a pointer.

```python
import sys

assert sys.getsizeof([b'x']) == sys.getsizeof([b'x' * 1_000_000])  # O(1)

class Measured:
    def __sizeof__(self):
        return 42

assert sys.getsizeof(Measured()) >= 42   # the GC header is added to what it returned

class Opaque:
    __slots__ = ()
    __sizeof__ = None

try:
    sys.getsizeof(Opaque())
except TypeError as error:
    assert 'not callable' in str(error)
else:
    raise AssertionError('an object with no __sizeof__ was measured anyway')

assert sys.getsizeof(Opaque(), 99) == 99  # the default is returned instead
```

## Asynchronous Generator Hooks

`sys.set_asyncgen_hooks()` stores two functions for the current thread. `firstiter` is called
once for each asynchronous generator, when it is first stepped - not once per step - so its
cost scales with generators created, not with iterations.

```python
import sys

started = []
sys.set_asyncgen_hooks(firstiter=started.append)   # O(1), per thread

async def numbers():
    yield 1
    yield 2

def step(awaitable):
    try:
        awaitable.send(None)
    except StopIteration as stop:
        return stop.value
    raise AssertionError('the step did not finish')

generator = numbers()
assert step(generator.__anext__()) == 1
assert step(generator.__anext__()) == 2
assert len(started) == 1                  # once per generator, not once per step

sys.set_asyncgen_hooks(None, None)        # O(1)
assert sys.get_asyncgen_hooks() == (None, None)
```

## Common Patterns

### Reporting the Caller's Location

```python
import sys

def caller_location(depth=1):
    frame = sys._getframe(depth + 1)   # O(d) - one link per level
    return frame.f_code.co_name, frame.f_lineno

def helper():
    return caller_location()

def entry():
    return helper()

name, _ = entry()
assert name == 'entry'
```

### Printing a Traceback Without Raising

```python
import io
import sys

def inner():
    raise ValueError('boom')

def outer():
    inner()

report = io.StringIO()
original = sys.stderr
sys.stderr = report
try:
    outer()
except ValueError:
    sys.excepthook(*sys.exc_info())   # O(d + s + m) - three distinct frames, so three entries
finally:
    sys.stderr = original

text = report.getvalue()
assert text.count('  File "') == 3    # this block, outer, inner
assert text.rstrip().endswith('ValueError: boom')
```

## Performance Best Practices

✅ **Do**:

- Reach for `sys._getframe(0)` or `sys._getframe(1)` and let something else walk further; the
  cost is the depth you ask for
- Prepend to `sys.path` with a slice assignment: O(e + k) once, rather than O(k*e + k**2) for
  the same entries inserted one at a time
- Use `sys.stdlib_module_names` for a membership test and `sys.builtin_module_names` only when
  you need the tuple itself
- Prefer `sys.exception()` to `sys.exc_info()` on Python 3.11+ when you only want the exception
- Scope `sys.monitoring` with `set_local_events()` where one code object is what you are after

❌ **Avoid**:

- Leaving a `settrace()` function installed: on the thread that installed it, it is called for
  every frame entered and, unless it declines that frame by returning `None`, for every line and
  every exception inside it
- Leaving a `setprofile()` function installed: fewer events - calls and returns, Python and C -
  but the return value is ignored, so a frame cannot be declined. From Python 3.12 installing or
  removing either one stops every thread as well
- Installing an audit hook you may want back out; nothing removes one
- Interning strings you do not keep a reference to, and on Python 3.12.0 to 3.12.6 interning
  many distinct strings at all
- Treating `sys.getsizeof()` as the size of a container's contents - it is the size of the
  container
- Calling `sys.getallocatedblocks()` in a hot path; from Python 3.13 it pauses every thread to
  read its counters

## Version Notes

- **Python 3.10.7+**: `sys.set_int_max_str_digits()` and `sys.get_int_max_str_digits()` added,
  with `sys.flags.int_max_str_digits` and `sys.int_info.default_max_str_digits`
- **Python 3.11+**: `sys.exception()` and `sys.flags.safe_path` added, and
  `sys.setrecursionlimit()` began writing through to every thread state, which is where its O(t)
  comes from
- **Python 3.12+**: `sys.monitoring`, `sys.getunicodeinternedsize()`,
  `sys._getframemodulename()`, `sys.last_exc` and the stack trampoline calls added;
  `sys._current_exceptions()` maps each thread to an exception rather than to an `exc_info()`
  triple; `sys.settrace()` and `sys.setprofile()` moved onto the monitoring machinery, so
  installing one went from O(1) to O(f + C)
- **Python 3.12.0 to 3.12.6**: `sys.intern()` makes the string immortal, so interning many
  distinct strings never gives the memory back; 3.12.7 restored the mortal table
- **Python 3.13+**: `sys._is_interned()`, `sys._is_gil_enabled()`, `sys.flags.gil` and
  `sys._clear_internal_caches()` added, and `sys._clear_type_cache()` documented as deprecated
  in favour of the last of those
- **Python 3.14+**: calling `sys._clear_type_cache()` raises `DeprecationWarning`;
  `sys.remote_exec()`, `sys.is_remote_debug_enabled()`, `sys._is_immortal()`, `sys._jit` and
  `sys.monitoring.clear_tool_id()` added, and `sys.monitoring.free_tool_id()` began clearing the
  tool's events and callbacks instead of only releasing the name
- **All Python 3**: an audit hook cannot be removed once added, so install one for the life of
  the process or not at all

## Related Modules

- **[traceback](traceback.md)** - formats the frames `sys.excepthook` prints
- **[threading](threading.md)** - the threads the O(t) rows count
- **[importlib](importlib.md)** - the finders behind `sys.meta_path` and `sys.path_hooks`
- **[gc](gc.md)** - reaches the objects `sys.getsizeof()` deliberately does not
- **[tracemalloc](tracemalloc.md)** - allocation totals, where `sys.getallocatedblocks()` gives
  one number
