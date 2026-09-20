# Built-in Exceptions Complexity

An exception is an ordinary object that a `raise` statement carries up the stack. Building one
usually just references what it was handed, so a message costs nothing to attach however long it
is. The work is in the propagation: every frame the exception passes through appends an entry to
its traceback, and every `except` clause it meets tests the classes that clause names against the
raised class.

The traceback is the part that grows with distance, and the part that surprises people about
lifetime: while the exception is reachable, so are the frames it unwound and every local those
frames held. It is not the only thing an exception keeps alive — `args`, `AttributeError.obj`, a
`__context__` chain and a group's children all hold references too — but it is the one that grows
without anyone putting anything in it.

`d` is the frames unwound between a `raise` and the handler that catches it, `t` is the classes
named in an `except` clause, `a` is the raised class's ancestors, `c` is the exceptions linked
through `__context__` or `__cause__`, `m` is a group's direct children, `n` is the nodes in a
group's whole tree — nested groups as well as leaves — and `p` is the notes attached to one
exception, or in a group bound the most on any one of its groups. Every constructor bound here
treats the number of arguments as fixed — it is one in
nearly all of them — and every group bound treats a predicate call as constant. A referenced
payload's size then reaches only one time bound on this page, the failed `decode()` below:
`ValueError` holds the string it was given rather than a copy, so a one-megabyte message and a
one-character message cost the same to build, raise and catch. A group's children are the
exception, since the constructor walks the collection it is handed rather than just keeping it.

## Complexity Reference

### Raising and catching

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `raise exc`, propagating d frames | O(d) | O(d) | One traceback entry per frame unwound |
| `raise`, with no argument | O(1) | O(1) | Re-raises the exception being handled; the unwinding that follows costs as above. `raise error` instead appends the current frame a second time |
| `raise new from old` | O(1) | O(1) | Sets `__cause__` and `__suppress_context__`; the link is a reference |
| Raising inside an `except` block | O(c) | O(1) | Setting `__context__` walks the chain already attached to the exception being handled, to avoid closing a cycle |
| Matching an `except` clause | O(t·a) worst case | O(1) | Every class named is checked for being an exception class, whether or not an earlier one already matched; the raised class's ancestors are then scanned once per candidate until one matches, so a match in the first position pays a only once. Both counts come from the source, not from the data, and both are small in ordinary code |
| `except ... as name` | O(1), plus the teardown above when the block ends | O(1) | The name is deleted when the block ends, giving up the reference the handler held; whether the d entries go with it depends on whether anything else kept the exception |
| `try`/`except`/`else`/`finally` with nothing raised | O(1) | O(1) | Entering and leaving the block is not priced per statement inside it |

### BaseException

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseException(*args)`, and every subclass below | O(1) | O(1) | Arguments are referenced, not copied. `OSError`, the `UnicodeError`s and the group classes add work of their own, priced in their own tables |
| `BaseException.args` | O(1) | O(1) | The tuple built at construction; `OSError` and `SyntaxError` keep some of their state off it |
| `BaseException.with_traceback(tb)` | O(1), plus O(d) when it drops the last reference | O(1) | Returns the same exception. `with_traceback(None)` gives up this exception's claim on d frames; the entries are freed in that call only if nothing else still holds them |
| `BaseException.add_note(note)` | O(1) amortized | O(1) | Appends to `__notes__`, creating the list on the first call. Python 3.11+ |
| `BaseException.__notes__` | O(1) | O(p) | p = notes attached; the attribute does not exist until `add_note()` is called. Python 3.11+ |
| `BaseException.__traceback__` | O(1) | O(d) | Reading it is a reference; keeping it is what holds the frames |
| `BaseException.__cause__`, `.__context__`, `.__suppress_context__` | O(1) | O(1) | References. A chain of c linked exceptions is c objects held; formatting follows `__cause__` where one is set, and otherwise `__context__` unless `__suppress_context__` stops it |
| `Exception` | O(1) | O(1) | The base of everything ordinary code should catch |

### Errors that carry only their arguments

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ArithmeticError`, `FloatingPointError`, `OverflowError`, `ZeroDivisionError` | O(1) | O(1) | `OverflowError` is a float result out of range or an integer too large to convert; Python integers do not overflow |
| `LookupError`, `IndexError`, `KeyError` | O(1) | O(1) | The failed key reaches `args` by reference, so an expensive key costs nothing extra to report |
| `TypeError`, `ValueError` | O(1) | O(1) | |
| `AssertionError` | O(1) | O(1) | The `assert` that would raise it is not compiled under `-O` |
| `BufferError` | O(1) | O(1) | Raised when an exported buffer blocks a resize |
| `EOFError` | O(1) | O(1) | `input()` at end of input; `read()` returns `''` instead |
| `MemoryError` | O(1) | O(1) | The interpreter keeps pre-allocated instances so that one can be raised when allocation is already failing |
| `ReferenceError` | O(1) | O(1) | From a `weakref.proxy` whose referent is gone; a plain `weakref.ref` returns `None` instead |
| `RuntimeError`, `NotImplementedError`, `RecursionError` | O(1) | O(1) | |
| `PythonFinalizationError` | O(1) | O(1) | An operation blocked during interpreter shutdown. Python 3.13+; the operations it replaced raised a plain `RuntimeError` before that |
| `SystemError` | O(1) | O(1) | An interpreter bug, not a program error |
| `StopIteration`, `StopIteration.value` | O(1) | O(1) | `value` carries a generator's return value |
| `StopAsyncIteration` | O(1) | O(1) | |
| `SystemExit`, `SystemExit.code` | O(1) | O(1) | Raised by `sys.exit()`; not an `Exception` subclass |
| `KeyboardInterrupt`, `GeneratorExit` | O(1) | O(1) | Not `Exception` subclasses either, so `except Exception` lets all three through |

### Errors that name what could not be found

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `NameError`, `NameError.name` | O(1) | O(1) | The unresolved identifier |
| `UnboundLocalError` | O(1) | O(1) | A `NameError` subclass; it inherits `name` but leaves it `None` |
| `AttributeError`, `AttributeError.name`, `AttributeError.obj` | O(1) | O(1) | `obj` is a reference to the object searched, so a caught `AttributeError` keeps it alive |
| `ImportError`, `ImportError.name`, `ImportError.path` | O(1) | O(1) | `path` is the file of the module the import reached, set when one was found — including a loaded module that simply lacks the requested name; it is `None` when nothing was found |
| `ModuleNotFoundError` | O(1) | O(1) | An `ImportError` subclass raised when the import found no module to load |

### OSError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OSError(errno, strerror[, filename[, winerror[, filename2]]])` | O(1) | O(1) | A recognised `errno` selects a subclass at construction, so `OSError(...)` can return a `FileNotFoundError` |
| `OSError.errno`, `.strerror` | O(1) | O(1) | Both also appear in `args` |
| `OSError.filename`, `.filename2` | O(1) | O(1) | Attributes only; the two-argument `args` never grows to hold them |
| `OSError.winerror` | O(1) | O(1) | Windows only; the attribute is absent on other platforms |
| `BlockingIOError`, `BlockingIOError.characters_written` | O(1) | O(1) | The attribute is unset until a partial write reports one, so reading it first raises `AttributeError` |
| `FileExistsError`, `FileNotFoundError`, `IsADirectoryError`, `NotADirectoryError`, `PermissionError` | O(1) | O(1) | Path errors, selected by `errno` |
| `ChildProcessError`, `InterruptedError`, `ProcessLookupError`, `TimeoutError` | O(1) | O(1) | `TimeoutError` is an `OSError`; `socket.timeout` became an alias of it in Python 3.10 and `asyncio.TimeoutError` in 3.11 |
| `ConnectionError`, `BrokenPipeError`, `ConnectionAbortedError`, `ConnectionRefusedError`, `ConnectionResetError` | O(1) | O(1) | |
| `EnvironmentError`, `IOError` | O(1) | O(1) | Names bound to `OSError` itself, not subclasses |

### UnicodeError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `UnicodeError` | O(1) | O(1) | A `ValueError` subclass |
| `UnicodeDecodeError(encoding, object, start, end, reason)`, `object` a `bytes` | O(1) | O(1) | It references the buffer. Any other buffer is converted to `bytes` first, which copies it |
| A `UnicodeDecodeError` raised by a failed `decode()` | O(len(object)) | O(len(object)) | The exception is built from the decoder's buffer, so it copies the whole input however early the failure is |
| `UnicodeEncodeError` from a failed `encode()` | O(1) | O(1) | Holds the original `str`, not a copy |
| `UnicodeTranslateError` | O(1) | O(1) | Raised by codec error handlers during translation |
| `UnicodeError.encoding`, `.object`, `.start`, `.end`, `.reason` | O(1) | O(1) | Reads; `object` is what keeps the input alive |

`str.encode()` gives its exception the original string, so only the failed `decode()` pays for the
whole input. It pays for it even when the first byte is the bad one: the scan stops at the failure,
but the copy does not — the exception is given the entire buffer either way.

### SyntaxError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `SyntaxError` | O(1) | O(1) | Raised while parsing, so the code it describes never runs; it propagates from the `compile()`, `exec()` or `import` that started the parse |
| `SyntaxError.msg`, `.filename`, `.lineno`, `.offset`, `.text` | O(1) | O(1) | `text` holds the offending line, not the source around it; `offset` is 1-indexed. The wording of `msg` is not stable across releases |
| `SyntaxError.end_lineno`, `.end_offset` | O(1) | O(1) | The end of the highlighted span; `end_offset` moved by one for some errors between Python 3.10 and 3.14 |
| `IndentationError` | O(1) | O(1) | A `SyntaxError` subclass |
| `TabError` | O(1) | O(1) | An `IndentationError` subclass, raised only for indentation that mixes tabs and spaces inconsistently — uneven indentation on its own is a plain `IndentationError` |

### Exception groups

Available from Python 3.11.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `BaseExceptionGroup(message, exceptions)` | O(m) | O(m) | m = direct children, each type-checked; an already-built child subtree is not walked. The result is an `ExceptionGroup` when every leaf is an `Exception`, and a `BaseExceptionGroup` otherwise |
| `ExceptionGroup(message, exceptions)` | O(m) | O(m) | Rejects a direct child that is not an `Exception` |
| `BaseExceptionGroup.message` | O(1) | O(1) | Also `args[0]` |
| `BaseExceptionGroup.exceptions` | O(1) | O(1) | The m direct children, not the leaves |
| `BaseExceptionGroup.subgroup(cond)` | O(n·(1 + p)) worst case | O(n·(1 + p)) | Tests the group itself first and keeps the whole subtree if it matches; otherwise descends. Returns `None` when nothing matches, having walked all n. Every group it rebuilds gets a fresh copy of that group's own notes, so p is paid once per rebuilt group rather than once overall |
| `BaseExceptionGroup.split(cond)` | O(n·(1 + p)) worst case | O(n·(1 + p)) | The same walk and the same per-group note copying, building both halves |
| `BaseExceptionGroup.derive(excs)` | O(len(excs)) | O(len(excs)) | Builds a sibling group with the same message and no traceback, cause, context or notes; `split()` and `subgroup()` copy all of those onto the groups they return |
| `except*` | O(n·(1 + p)) worst case | O(n·(1 + p)) | Each clause splits what is left of the group, so k clauses cost up to k walks |

### Warning categories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Warning` | O(1) | O(1) | An `Exception` subclass; a warning is only an exception that is normally not raised |
| `UserWarning`, `DeprecationWarning`, `PendingDeprecationWarning`, `FutureWarning`, `SyntaxWarning`, `RuntimeWarning`, `ImportWarning`, `UnicodeWarning`, `BytesWarning`, `ResourceWarning` | O(1) | O(1) | Categories, used to select a filter |
| `EncodingWarning` | O(1) | O(1) | Emitted for a text file opened without an explicit encoding under `-X warn_default_encoding` |

What issuing a warning costs — filter matching and the once-per-location registry — belongs to the
[warnings](../stdlib/warnings.md) module, not to these classes.

## The Exception Hierarchy

Catching a base class catches everything under it, so where a class sits decides what a handler
sweeps up.

```
BaseException
├── SystemExit
├── KeyboardInterrupt
├── GeneratorExit
├── BaseExceptionGroup
└── Exception
    ├── ArithmeticError
    │   ├── FloatingPointError
    │   ├── OverflowError
    │   └── ZeroDivisionError
    ├── AssertionError
    ├── AttributeError
    ├── BufferError
    ├── EOFError
    ├── ExceptionGroup            (also a BaseExceptionGroup)
    ├── ImportError
    │   └── ModuleNotFoundError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── MemoryError
    ├── NameError
    │   └── UnboundLocalError
    ├── OSError                   (also named EnvironmentError and IOError)
    │   ├── BlockingIOError
    │   ├── ChildProcessError
    │   ├── ConnectionError
    │   │   ├── BrokenPipeError
    │   │   ├── ConnectionAbortedError
    │   │   ├── ConnectionRefusedError
    │   │   └── ConnectionResetError
    │   ├── FileExistsError
    │   ├── FileNotFoundError
    │   ├── InterruptedError
    │   ├── IsADirectoryError
    │   ├── NotADirectoryError
    │   ├── PermissionError
    │   ├── ProcessLookupError
    │   └── TimeoutError
    ├── ReferenceError
    ├── RuntimeError
    │   ├── NotImplementedError
    │   ├── PythonFinalizationError
    │   └── RecursionError
    ├── StopAsyncIteration
    ├── StopIteration
    ├── SyntaxError
    │   └── IndentationError
    │       └── TabError
    ├── SystemError
    ├── TypeError
    ├── ValueError
    │   └── UnicodeError
    │       ├── UnicodeDecodeError
    │       ├── UnicodeEncodeError
    │       └── UnicodeTranslateError
    └── Warning
        ├── BytesWarning
        ├── DeprecationWarning
        ├── EncodingWarning
        ├── FutureWarning
        ├── ImportWarning
        ├── PendingDeprecationWarning
        ├── ResourceWarning
        ├── RuntimeWarning
        ├── SyntaxWarning
        ├── UnicodeWarning
        └── UserWarning
```

`SystemExit`, `KeyboardInterrupt` and `GeneratorExit` sit outside `Exception` on purpose, and
`BaseExceptionGroup` joins them from Python 3.11. `except Exception` lets all of them through,
which is what makes it safe where a bare `except:` is not.

```python
import builtins
import sys

assert issubclass(Exception, BaseException)

outside = [SystemExit, KeyboardInterrupt, GeneratorExit]
if sys.version_info >= (3, 11):
    outside.append(builtins.BaseExceptionGroup)

for cls in outside:
    assert issubclass(cls, BaseException)
    assert not issubclass(cls, Exception)

# So an `except Exception` ahead of a more specific clause does not shadow it
outcome = None
try:
    raise SystemExit(3)
except Exception:          # O(t*a) - tested first, and does not match
    outcome = "swallowed"
except SystemExit as error:
    outcome = error.code   # O(1)
assert outcome == 3
```

## What a Raise Costs

### The Traceback Grows with the Stack

Each frame the exception unwinds adds one traceback entry, so propagation is linear in the
distance between the `raise` and the handler. Nothing else about the exception grows.

```python
import traceback

def descend(depth):
    if depth:
        return descend(depth - 1)
    raise ValueError("bottom")

def entries(depth):
    try:
        descend(depth)  # O(depth) to propagate
    except ValueError as error:
        return len(traceback.extract_tb(error.__traceback__))  # O(depth)
    raise AssertionError("descend() returned")

assert entries(0) == 2      # the `try` itself, then descend
assert entries(100) == 102  # one more entry per frame unwound
assert entries(400) == 402
```

### A Held Traceback Holds Its Frames

The traceback references the frames, and a frame references its locals. Keeping the exception
therefore keeps all d frames and everything in them. `with_traceback(None)` gives that up; when it
drops the last reference, the d entries are freed in that call rather than later.

```python
import gc
import weakref

tracker = None

class Payload:
    pass

def fail():
    global tracker
    payload = Payload()
    tracker = weakref.ref(payload)
    raise ValueError("boom")

try:
    fail()
except ValueError as error:
    held = error  # keeping the exception keeps its traceback

assert tracker() is not None  # fail()'s frame, and its local, are still reachable

held.with_traceback(None)  # O(d) - frees the entries, releasing the frames with them
gc.collect()
assert tracker() is None
```

Binding with `except ... as name` does this for you, as far as the handler's own reference goes:
the name is deleted when the block ends. It is storing the exception past the block — in a list, a
retry record, a log entry object — that keeps the frames, because something still points at them.

### Matching an except Clause

Clauses are tried in source order and the first match wins, so a base class written above a
subclass makes the subclass unreachable. Every class in a tuple is validated whether or not an
earlier entry already matched; the ancestor scan then runs per candidate until one matches, which
is why the two terms multiply in the worst case rather than adding. Putting the likely class first
pays the ancestor scan once.

```python
class AppError(Exception):
    pass

class ValidationError(AppError):
    pass

try:
    raise ValidationError("bad field")
except (KeyError, ValidationError, AppError) as error:  # O(t*a), t = 3
    matched = type(error).__name__
assert matched == "ValidationError"

# Source order decides, not how specific the class is
try:
    raise ValidationError("bad field")
except AppError:
    first = "AppError"
except ValidationError:
    first = "ValidationError"
assert first == "AppError"

# The whole tuple is checked, so a bad entry is rejected even behind a match
try:
    try:
        raise ValidationError("bad field")
    except (ValidationError, "not a class"):
        pass
except TypeError as error:
    assert "do not inherit from BaseException" in str(error)
else:
    raise AssertionError("a non-class entry was accepted")
```

## Payloads Are References

An exception stores what it was handed. Building `ValueError(message)` neither copies nor measures
the message, so the size of what went wrong never shows up in the cost of reporting it.

```python
message = "x" * 1_000_000

error = ValueError(message)  # O(1) - the string is referenced, not copied
assert error.args[0] is message
assert error.args == (message,)

# The same holds for a key that was expensive to build
key = tuple(range(100_000))
try:
    {}[key]
except KeyError as missing:  # O(1)
    assert missing.args[0] is key
else:
    raise AssertionError("an empty dict had the key")
```

### OSError Splits Its State

`OSError`'s constructor sorts its arguments rather than just keeping them: a recognised `errno`
selects a subclass, and the filenames land on attributes rather than in `args`.

```python
import errno

error = OSError(errno.ENOENT, "No such file or directory", "missing.txt")  # O(1)

assert type(error) is FileNotFoundError  # errno picked the subclass
assert error.errno == errno.ENOENT
assert error.strerror == "No such file or directory"
assert error.filename == "missing.txt"
assert error.filename2 is None
assert error.args == (errno.ENOENT, "No such file or directory")  # filename is not in args

assert type(OSError(errno.EACCES, "denied")) is PermissionError
assert type(OSError(errno.EPIPE, "broken")) is BrokenPipeError
assert type(OSError(errno.ESRCH, "no process")) is ProcessLookupError
assert type(OSError(errno.ECHILD, "no child")) is ChildProcessError
assert type(OSError(errno.EINTR, "interrupted")) is InterruptedError
assert type(OSError(errno.EEXIST, "exists")) is FileExistsError
assert type(OSError(errno.EISDIR, "is a directory")) is IsADirectoryError
assert type(OSError(errno.ENOTDIR, "not a directory")) is NotADirectoryError
assert type(OSError(errno.ECONNRESET, "reset")) is ConnectionResetError
assert type(OSError(errno.ECONNREFUSED, "refused")) is ConnectionRefusedError
assert type(OSError(errno.ECONNABORTED, "aborted")) is ConnectionAbortedError
assert issubclass(ConnectionResetError, ConnectionError)

# The old names are the class itself, so they catch every subclass above
assert EnvironmentError is OSError and IOError is OSError
assert issubclass(TimeoutError, OSError)

# `characters_written` is unset until a partial write reports one
blocked = BlockingIOError(errno.EAGAIN, "write would block")
assert not hasattr(blocked, "characters_written")
blocked.characters_written = 512  # O(1)
assert blocked.characters_written == 512
```

The five-argument form fills `filename2`; the fourth slot is `winerror`, which exists as an
attribute only on Windows.

```python
import errno
import sys

error = OSError(errno.EXDEV, "Invalid cross-device link", "a.txt", None, "b.txt")  # O(1)

assert error.filename == "a.txt"
assert error.filename2 == "b.txt"
assert hasattr(error, "winerror") == (sys.platform == "win32")
```

### A Failed Decode Copies Its Input

`str.encode()` hands the exception the original string. `bytes.decode()` does not: the exception
is built from the decoder's own buffer, so a failed decode holds the input twice until the
exception is released. That is the one O(size) space term on this page.

```python
data = b"\xff" * 100_000

try:
    # The scan stops at byte 0; the exception is still built from all 100,000
    data.decode("utf-8")  # O(len(data))
except UnicodeDecodeError as failure:
    assert failure.object == data
    assert failure.object is not data  # a copy, held for the exception's lifetime
    assert failure.encoding == "utf-8"
    assert failure.start == 0 and failure.end == 1
    assert failure.reason == "invalid start byte"
else:
    raise AssertionError("invalid UTF-8 decoded")

text = "\ud800" * 100_000

try:
    text.encode("utf-8")  # O(len(text)) to scan, and nothing to copy
except UnicodeEncodeError as failure:
    assert failure.object is text  # the original, referenced
    assert failure.encoding == "utf-8"
else:
    raise AssertionError("a lone surrogate encoded")

# Built directly, the decode error references its buffer like any other exception
direct = UnicodeDecodeError("utf-8", data, 0, 1, "invalid start byte")  # O(1)
assert direct.object is data
assert isinstance(UnicodeError("generic"), ValueError)
assert issubclass(UnicodeTranslateError, UnicodeError)
```

### Where the Source Went Wrong

`SyntaxError` carries the position of the problem rather than the source around it: `text` is the
offending line alone, not the file, and every attribute is an O(1) read.

```python
try:
    compile("if True\n    pass\n", "demo.py", "exec")  # O(1) to report, once parsed
except SyntaxError as error:
    assert isinstance(error.msg, str)
    assert error.filename == "demo.py"
    assert error.lineno == 1
    assert error.offset == 8  # 1-indexed
    assert error.text == "if True\n"
    assert error.end_lineno == 1
    assert error.end_offset >= error.offset
else:
    raise AssertionError("a colon-less `if` compiled")

# Uneven indentation is an IndentationError
try:
    compile("if True:\npass\n", "demo.py", "exec")
except TabError:
    raise AssertionError("uneven indentation reported as a tab problem")
except IndentationError as error:
    assert error.lineno == 2
else:
    raise AssertionError("an unindented block compiled")

# TabError is for tabs and spaces used inconsistently, and only for that
try:
    compile("if True:\n  pass\n\tpass\n", "demo.py", "exec")
except TabError as error:
    assert error.lineno == 3
    assert error.text == "\tpass\n"
else:
    raise AssertionError("mixed tabs and spaces compiled")

assert issubclass(TabError, IndentationError)
assert issubclass(IndentationError, SyntaxError)
```

### Names, Attributes and Imports

Each of these records what it could not resolve, at no extra cost. `AttributeError.obj` is a
reference to the object that was searched, so a stored `AttributeError` keeps that object alive
the way a traceback keeps a frame.

```python
try:
    undefined_name  # noqa: B018 - the point is that it does not resolve
except NameError as error:
    assert error.name == "undefined_name"  # O(1)
else:
    raise AssertionError("an unbound name resolved")

class Config:
    host = "localhost"

try:
    Config.port
except AttributeError as error:
    assert error.name == "port"
    assert error.obj is Config  # a reference, not a repr
else:
    raise AssertionError("a missing attribute resolved")

try:
    import no_such_module_here
except ModuleNotFoundError as error:
    assert isinstance(error, ImportError)
    assert error.name == "no_such_module_here"
    assert error.path is None  # set when the import reached a module's file
else:
    raise AssertionError("a missing module imported")

def read_before_write():
    try:
        return count
    except UnboundLocalError as error:
        return error.name
    count = 0  # noqa: F841 - unreachable, but it makes `count` local

assert read_before_write() is None  # inherited from NameError, never filled in
assert issubclass(UnboundLocalError, NameError)
```

## Chaining

`raise ... from ...` sets `__cause__`; raising inside an `except` block sets `__context__` whether
you ask for it or not. Both are single references, so a chain costs one link per exception — but
everything in the chain stays alive, and formatting it walks all c of them.

```python
def load(raw):
    try:
        return int(raw)
    except ValueError as error:
        raise TypeError(f"not a count: {raw!r}") from error  # O(1)

try:
    load("twelve")
except TypeError as error:
    assert isinstance(error.__cause__, ValueError)  # O(1)
    assert error.__cause__ is error.__context__
    assert error.__suppress_context__ is True
else:
    raise AssertionError("'twelve' parsed")

# Without `from`, the context is still linked; only the display changes
try:
    try:
        int("twelve")
    except ValueError:
        raise TypeError("not a count")
except TypeError as error:
    assert isinstance(error.__context__, ValueError)
    assert error.__cause__ is None
    assert error.__suppress_context__ is False

# `from None` drops the display without unlinking anything
try:
    try:
        int("twelve")
    except ValueError:
        raise TypeError("not a count") from None
except TypeError as error:
    assert error.__cause__ is None
    assert isinstance(error.__context__, ValueError)
    assert error.__suppress_context__ is True
```

## Notes

`add_note()` appends to a plain list that does not exist until the first call, so an exception that
is never annotated carries no note storage at all.

```python
import sys

error = ValueError("bad row")
assert not hasattr(error, "__notes__")  # nothing allocated yet

if sys.version_info >= (3, 11):
    error.add_note("row 14")  # O(1) amortized - a list append
    error.add_note("file inventory.csv")
    assert error.__notes__ == ["row 14", "file inventory.csv"]
    assert error.args == ("bad row",)  # notes are not arguments
```

## Exception Groups

A group is a tree. Building one checks its direct children and nothing below them, so an
already-built subtree costs nothing to nest. `split()`, `subgroup()` and `except*` are the walks:
each tests a node before descending into it, so a node that matches keeps its whole subtree
untouched, and a walk that matches nothing visits all n. Each group they rebuild is handed a copy
of that group's traceback, context, cause and notes — the notes once per group, which is why p
multiplies rather than adds.

```python
import sys

if sys.version_info >= (3, 11):
    first = ValueError("v1")
    inner = ExceptionGroup("inner", [TypeError("t"), ValueError("v2")])
    group = ExceptionGroup("outer", [first, inner])  # O(m) - two direct children

    assert group.message == "outer"  # O(1)
    assert group.args == ("outer", [first, inner])  # the children, by reference
    assert group.exceptions == (first, inner)  # O(1) - direct children, not leaves
    assert len(group.exceptions) == 2

    visited = []

    def is_value_error(exc):
        visited.append(type(exc).__name__)
        return isinstance(exc, ValueError)

    matched, rest = group.split(is_value_error)  # O(n) - nothing matches above a leaf

    assert visited == ["ExceptionGroup", "ValueError", "ExceptionGroup", "TypeError", "ValueError"]
    assert len(matched.exceptions) == 2
    assert isinstance(rest, ExceptionGroup)

    assert group.subgroup(TypeError).message == "outer"  # O(n)
    assert group.subgroup(KeyError) is None  # O(n) even with nothing to return

    # A node that matches is kept whole, so the walk stops there
    stopped = []

    def matches_anything(exc):
        stopped.append(type(exc).__name__)
        return True

    assert group.subgroup(matches_anything) is group
    assert stopped == ["ExceptionGroup"]

    derived = group.derive([KeyError("k")])  # O(len(excs))
    assert derived.message == "outer"
    assert derived.__traceback__ is None  # split() and subgroup() copy it; derive() does not

    # The class follows the leaves
    assert type(BaseExceptionGroup("g", [ValueError("v")])) is ExceptionGroup
    assert type(BaseExceptionGroup("g", [KeyboardInterrupt()])) is BaseExceptionGroup
```

`except*` splits per clause, so a group met by k clauses costs up to k walks.

```python
import sys

# `except*` is a syntax error before Python 3.11, so the source is compiled at run time
SOURCE = """
try:
    raise ExceptionGroup("boom", [ValueError(1), TypeError(2), ValueError(3)])
except* ValueError as group:      # O(n) to split
    caught.append(("ValueError", len(group.exceptions)))
except* TypeError as group:       # O(n) again, over what is left
    caught.append(("TypeError", len(group.exceptions)))
"""

caught = []
if sys.version_info >= (3, 11):
    exec(SOURCE, {"caught": caught, "ExceptionGroup": ExceptionGroup})
    assert caught == [("ValueError", 2), ("TypeError", 1)]
```

## Generators and StopIteration

A generator signals exhaustion with `StopIteration`, which makes a `StopIteration` raised *inside*
one ambiguous. Since Python 3.7 the interpreter converts it, so the bug surfaces as a
`RuntimeError` with the original on `__context__` rather than as a silently short iterator.

```python
def leaks_stop_iteration():
    yield 1
    raise StopIteration("not a return")

generator = leaks_stop_iteration()
assert next(generator) == 1

try:
    next(generator)
except RuntimeError as error:  # O(1)
    assert isinstance(error.__context__, StopIteration)
else:
    raise AssertionError("StopIteration escaped the generator")

# A return value rides on StopIteration.value instead
def returns_total():
    yield 1
    return 42

totals = returns_total()
assert next(totals) == 1

try:
    next(totals)
except StopIteration as stop:
    assert stop.value == 42  # O(1)
else:
    raise AssertionError("the generator yielded again")
```

## Reading a Traceback

Formatting walks every exception the display will show — the c links, and every node of a group —
and every frame of each one's traceback, so its cost is all of those together before the output
itself is built. One link's d is not the whole of it, and a group with no traceback and no links
still costs its n nodes. It is linear in that total even when the text is short. A
`RecursionError` is the clearest case: the display folds the repeated frames, but each one is
still visited to discover that it repeats.

```python
import sys
import traceback

sys.setrecursionlimit(400)

def recurse():
    recurse()

try:
    recurse()
except RecursionError as error:
    frames = traceback.extract_tb(error.__traceback__)  # O(d)
    rendered = "".join(traceback.format_exception(error))  # O(d)
    assert len(frames) > 200  # every frame is walked
    assert "[Previous line repeated" in rendered
    assert len(rendered.splitlines()) < len(frames)  # and then folded for display
else:
    raise AssertionError("recursion did not stop")
```

`sys.exc_info()` and, from Python 3.11, `sys.exception()` reach the exception being handled without
it being bound to a name.

```python
import sys

try:
    1 / 0
except ZeroDivisionError:
    exc_type, exc_value, exc_traceback = sys.exc_info()  # O(1)
    assert exc_type is ZeroDivisionError
    assert exc_traceback is exc_value.__traceback__
    if sys.version_info >= (3, 11):
        assert sys.exception() is exc_value  # O(1)

assert sys.exc_info() == (None, None, None)  # nothing is being handled here
```

## Warnings

A warning category is an ordinary `Exception` subclass; what makes it a warning is that the
`warnings` machinery normally reports it instead of raising it.

```python
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    warnings.warn("check your input")  # O(1) - UserWarning by default
    warnings.warn("going away", DeprecationWarning)
    warnings.warn("not yet, but soon", PendingDeprecationWarning)
    warnings.warn("behaviour will change", FutureWarning)
    warnings.warn("unusual condition", RuntimeWarning)
    warnings.warn("odd syntax", SyntaxWarning)
    warnings.warn("import problem", ImportWarning)
    warnings.warn("unicode problem", UnicodeWarning)
    warnings.warn("bytes problem", BytesWarning)
    warnings.warn("no encoding given", EncodingWarning)
    warnings.warn("file left open", ResourceWarning)

categories = [type(entry.message).__name__ for entry in caught]
assert categories[0] == "UserWarning"
assert len(categories) == 11
assert all(issubclass(type(entry.message), Warning) for entry in caught)
assert issubclass(Warning, Exception)

# Turned into an error, a category behaves like any other exception
with warnings.catch_warnings():
    warnings.simplefilter("error", DeprecationWarning)
    try:
        warnings.warn("going away", DeprecationWarning)
    except DeprecationWarning as error:
        assert error.args == ("going away",)
    else:
        raise AssertionError("the filter did not raise")
```

## Common Patterns

### Keep the Message, Not the Exception

Collecting failures across a loop is where a traceback's O(d) space turns into O(rows·d). Keeping
the message instead costs one string per failure and holds no frames.

```python
rows = ["1", "x", "3", "y"]
failures = []

for row in rows:
    try:
        int(row)
    except ValueError as error:
        failures.append(str(error))  # one message held, against d frames for the exception

assert len(failures) == 2
assert failures[0].endswith("'x'")
```

### Narrow, Then Re-raise

Catching a base class to inspect and re-raise costs one `raise` with no argument, which keeps the
traceback that already exists rather than starting a new one.

```python
import errno
import traceback

def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as error:
        if error.errno == errno.ENOENT:  # O(1)
            return ""
        raise  # O(1) - the original traceback continues

assert read("definitely-not-here.txt") == ""

try:
    read(".")  # a directory, so a different errno
except IsADirectoryError as error:
    assert error.errno == errno.EISDIR
    assert len(traceback.extract_tb(error.__traceback__)) >= 2
else:
    raise AssertionError("reading a directory succeeded")
```

### A Custom Hierarchy

Giving an application one base class lets a caller choose its altitude: the specific error, the
family, or everything the application raises.

```python
class AppError(Exception):
    """Anything this application raises deliberately."""

class ValidationError(AppError):
    pass

class DatabaseError(AppError):
    pass

def handle(error):
    try:
        raise error
    except ValidationError:
        return "validation"
    except AppError:  # O(t*a) - one class, one ancestor step from DatabaseError
        return "application"

assert handle(ValidationError("bad field")) == "validation"
assert handle(DatabaseError("no connection")) == "application"
assert issubclass(ValidationError, AppError)
```

## Performance Best Practices

✅ **Do**:

- Catch `Exception` rather than writing a bare `except:`, so `SystemExit`, `KeyboardInterrupt` and
  `GeneratorExit` still travel
- Store what you will report — a message, an errno — instead of the exception, so a loop over
  failures does not hold d frames per failure
- Call `with_traceback(None)` on an exception you must keep, once you no longer need its frames
- Read `error.errno`, `error.name` or `error.filename` rather than parsing `str(error)`
- Put the specific `except` clause above the general one; the first match wins

❌ **Avoid**:

- Keeping a caught `UnicodeDecodeError` around: it holds a second copy of the buffer that failed,
  where a caught `UnicodeEncodeError` only references the original string
- Letting an `except Exception` sit above a clause for a subclass, which makes that clause dead
- Raising `StopIteration` inside a generator — it becomes a `RuntimeError`, not an early stop
- Re-raising with `raise error` where a bare `raise` would do: it appends to the traceback rather
  than continuing it

## Version Notes

- **Python 3.13+**: `PythonFinalizationError`, for operations blocked during interpreter shutdown;
  the operations it covered on arrival raised a plain `RuntimeError` before that, and 3.14 added
  `threading.Thread.join()` to them
- **Python 3.11+**: `ExceptionGroup`, `BaseExceptionGroup` and `except*`;
  `BaseException.add_note()` and `__notes__`; `sys.exception()`; `asyncio.TimeoutError` became an
  alias of `TimeoutError`
- **All Python 3.10+**: `NameError.name`, `AttributeError.name` and `.obj`,
  `SyntaxError.end_lineno` and `.end_offset`, `EncodingWarning`, and `socket.timeout` as an alias
  of `TimeoutError`
- **All Python 3**: `EnvironmentError` and `IOError` are `OSError` itself, so they catch every
  `OSError` subclass rather than a narrower set

## Related Modules

- **[warnings](../stdlib/warnings.md)** - what issuing a warning costs, and how filters select one
- **[traceback](../stdlib/traceback.md)** - O(d) formatting and extraction of what a raise recorded
- **[sys](../stdlib/sys.md)** - `sys.exc_info()`, `sys.exception()` and `sys.excepthook`
- **[\_\_debug\_\_](debug.md)** - why `AssertionError` disappears under `-O`
