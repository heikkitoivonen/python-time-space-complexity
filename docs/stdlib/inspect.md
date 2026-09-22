# inspect Module Complexity

The `inspect` module reads what the interpreter already holds: type flags, code objects, frames,
class dictionaries. Most of it is attribute access dressed up as a function, and costs accordingly.
The exceptions are the parts that leave the object graph — anything that reaches for source text
reads the defining file once and holds it, and anything that walks the stack does that once per
frame.

Sizes throughout. For a class: `m` is the names `dir()` reports, `c` the classes in its method
resolution order, `y` its metaclass chain's depth (1 for an ordinary class) and `h` the entries in
its `__dict__`. For a callable: `p` is the parameters in its signature, `a` the arguments supplied
to a call, `w` the links in a `__wrapped__`, `partial` or bound-method chain, and `r` the length of
a rendering where producing one is the operation. For a code object: `i` is its instructions, `g`
the global and attribute names it references, `f` its free variables, `v` its local variables and
`x` a frame's current offset into it. For source text: `F` is the lines in the defining file, `t`
the lines from a definition to the end of that file and `b` the lines in the definition's own
block. For a docstring: `n` is its characters, `L` its lines and `z` its leading blank ones.
Finally `d` is the frames on the stack and `M` the modules in `sys.modules`.

Two things are treated as O(1) throughout: reading one attribute with `getattr`, and one operation
on a short string such as a name, a path or a suffix. Everything counted above is a number of
*items* — lines, names, parameters, frames — not the characters inside one. The functions that walk
the MRO in Python rather than in C are priced in `c`.

## Complexity Reference

### Type and state predicates

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.isclass(object)`, `inspect.ismodule(object)`, `inspect.isfunction(object)`, `inspect.ismethod(object)`, `inspect.isbuiltin(object)`, `inspect.iscode(object)`, `inspect.isframe(object)`, `inspect.istraceback(object)` | O(1) | O(1) | One `isinstance` against a concrete type |
| `inspect.isgenerator(object)`, `inspect.iscoroutine(object)`, `inspect.isasyncgen(object)`, `inspect.isgetsetdescriptor(object)`, `inspect.ismemberdescriptor(object)` | O(1) | O(1) | Same shape; the last two are CPython extension-module descriptors |
| `inspect.ismethodwrapper(object)` | O(1) | O(1) | Python 3.11+; a slot wrapper bound to an instance, such as `object().__str__` |
| `inspect.isroutine(object)` | O(1) | O(1) | True for any function, method or method-like descriptor |
| `inspect.ismethoddescriptor(object)`, `inspect.isdatadescriptor(object)` | O(1) | O(1) | Looks for `__get__`, `__set__` and `__delete__` on the *type*, not the object. Before Python 3.13 `ismethoddescriptor()` did not test `__delete__`, so a descriptor defining `__get__` and `__delete__` but no `__set__` answered `True` to both |
| `inspect.isawaitable(object)` | O(1) | O(1) | Ends in an `abc.Awaitable` check, whose per-type result the ABC caches |
| `inspect.isgeneratorfunction(obj)`, `inspect.iscoroutinefunction(obj)`, `inspect.isasyncgenfunction(obj)` | O(w) | O(1) | Strips `partial`, `partialmethod` and bound-method layers before reading the code flag. Nesting plain partials collapses them, so `w` is normally 1; a partial that has been given an attribute does not collapse into its wrapper. `partialmethod` is stripped from Python 3.13 |
| `inspect.markcoroutinefunction(func)` | O(1) | O(1) | Python 3.12+; sets one marker attribute and returns the function |
| `inspect.isabstract(object)` | O(1) | O(1) | One `type.__flags__` bit. A class observed mid-construction, from `__init_subclass__`, takes a slower fallback over its own and its bases' abstract names |
| `inspect.ispackage(object)` | O(1) | O(1) | Python 3.14+; a module with `__path__` |
| `inspect.getgeneratorstate(generator)`, `inspect.getcoroutinestate(coroutine)`, `inspect.getasyncgenstate(agen)` | O(1) | O(1) | Three flag reads; `getasyncgenstate` is Python 3.12+ |
| `inspect.getgeneratorlocals(generator)`, `inspect.getcoroutinelocals(coroutine)`, `inspect.getasyncgenlocals(agen)` | O(1) from Python 3.13, O(v) before | O(1) from Python 3.13, O(v) before | Returns the frame's `f_locals`. From Python 3.13 that is a proxy built without reading the variables; before it, a dict the frame creates on first access and refreshes from them on every later one. `getasyncgenlocals` is Python 3.12+ |

### Members and attributes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.getmembers(object, predicate=None)` | O(m log m + descriptor cost) | O(m) | `dir()`, then one `getattr` per name, then a sort. Every property and descriptor on the object runs |
| `inspect.getmembers_static(object, predicate=None)` | O(m·c·y + m log m) | O(m + c) | Python 3.11+; same shape with `getattr_static`, so no property or descriptor is invoked, and each name walks the MRO in Python |
| `inspect.getattr_static(obj, attr, default)` | O(c·y) | O(c) from Python 3.12.10 and 3.13, O(1) before | Searches the instance dict and each MRO `__dict__` without invoking `__getattr__` or the descriptor protocol, checking each entry's metaclass for a shadowed `__dict__` as it goes. The newer versions build a weak reference per MRO entry on the way, so the space is no longer constant |
| `inspect.getmro(cls)` | O(1) | O(1) | Returns `cls.__mro__` itself — the existing tuple, not a copy |
| `inspect.classify_class_attrs(cls)` | O(m·(c + y)) | O(m + c + y) | For each name in `dir(cls)`, searches the MRO and then the metaclass MRO for its home class, having first joined the two into a tuple of its own |
| `inspect.Attribute` | O(1) | O(1) | The `(name, kind, defining_class, object)` named tuple `classify_class_attrs` yields |
| `inspect.getclasstree(classes, unique=False)` | O(e·q + T log T) | O(T) | q = classes given, e = their base links, T = entries in the returned tree; membership is tested against lists, so every base link rescans a child list. A class is repeated under every base it reaches, and its descendants with it, so T can far exceed q. `unique=True` stops at the first base that is itself in `classes` — it deduplicates within the list, not against bases outside it |
| `inspect.walktree(classes, children, parent)` | O(T log T) | O(T) | The recursive helper behind `getclasstree`, and what builds T; it sorts each sibling list **in place** |
| `inspect.isabstract(object)` | O(1) | O(1) | See the predicates table above |

### Documentation and comments

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.getdoc(object)` | O(n + z·L) | O(n) | `cleandoc()` on every call, with its leading-blank term; nothing is cached, though a docstring already clean on one line comes back unchanged. Falls back to an O(c) MRO search when `__doc__` is `None` |
| `inspect.cleandoc(doc)` | O(n + z·L) | O(n) | Expands tabs, measures the common margin, strips it from every line. Leading blank lines then come off one at a time, each shifting the rest, so a docstring that opens with many of them costs more than its length |
| `inspect.getcomments(object)` | O(F + j²) first call, then O(j²) | O(F) | j = comment lines found. Needs `findsource()` first — including its per-call O(F) parse for a class on Python 3.12 and earlier — then scans upward while the lines stay comments at the same indent, prepending each to a list. For a module it instead skips forward over the leading blank lines, which is O(F) when there are no comments to find |
| `inspect.get_annotations(obj, *, globals=None, locals=None, eval_str=False, format=...)` | O(annotations), plus h for a class before Python 3.14 and w with `eval_str=True` | O(annotations), plus h for a class before Python 3.14 | A fresh dict every call, excluding what evaluating an annotation costs. Before Python 3.14 a class's whole `__dict__` is copied first, whether or not it is annotated. `eval_str=True` first unwinds the `__wrapped__` and `partial` chain to find the globals to evaluate in, then compiles and evaluates each string annotation. `format` is Python 3.14+ |
| `inspect.formatannotation(annotation, base_module=None)` | O(r) | O(r) | A `typing` annotation is `repr`'d and then regex-substituted |
| `inspect.formatannotationrelativeto(object)` | O(1) | O(1) | Returns a formatter closed over `object.__module__` |

### Source retrieval

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.getfile(object)` | O(1) | O(1) | An attribute read, or one `sys.modules` lookup for a class |
| `inspect.getmodulename(path)` | O(1) | O(1) | Sorts the handful of registered import suffixes and matches the basename |
| `inspect.getsourcefile(object)` | O(1), O(M) for a path that does not exist | O(1), O(M) for a path that does not exist | `getfile()`, a suffix test and an `os.path.exists` stat. A path that is neither on disk nor in `linecache` falls through to `getmodule()`, which scans `sys.modules` and caches nothing on a miss. Returns `None` for an extension module |
| `inspect.getabsfile(object, _filename=None)` | O(1), O(M) for a path that does not exist | O(1), O(M) for a path that does not exist | `getsourcefile()` normalised through `abspath`, so it inherits that scan unless `_filename` is supplied |
| `inspect.getmodule(object, _filename=None)` | O(1) with `__module__`, O(M) otherwise | O(M) | A `sys.modules` lookup when the object has `__module__`. A code object or frame has none, so it falls back to mapping every loaded module by file into `inspect.modulesbyfile`. Only matches are cached, so a file belonging to no loaded module is rescanned on **every** call |
| `inspect.findsource(object)` | O(F) first call for a file, then O(1) | O(F) | Reads the file into `linecache` once; later calls hand back the cached lines and read the definition's index off the object. It asks `getmodule()` for the file each time, so the O(1) assumes that resolves. Python 3.12 and earlier do not: a class re-parses the file's AST on **every** call, and a code object is walked backwards from its first line to the `def`, `lambda` or decorator above it |
| `inspect.getsourcelines(object)` | O(F + t + w) first call, then O(t + w) | O(F + w) first call, then O(t + w) | `unwrap()`, then `findsource()`, then slices from the definition to the end of the file and tokenizes until the block closes. The cost is what *follows* the definition, not the definition's own size — except for a class on Python 3.12 and earlier, which pays `findsource()`'s O(F) parse every call |
| `inspect.getsource(object)` | O(F + t + w) first call, then O(t + w) | O(F + w) first call, then O(t + w) | `getsourcelines()` joined into one string, with the same class caveat |
| `inspect.getblock(lines)` | O(b), up to O(lines) | O(b) | Tokenizes until the first block ends, which is normally the block. Only a statement closes it, so a definition followed by nothing but blanks or comments is tokenized to the end of the list |
| `inspect.indentsize(line)` | O(line length) | O(line length) | The one row here counted in characters rather than items: `expandtabs()` builds a new string from the whole line |
| `inspect.BlockFinder`, `inspect.ClassFoundException`, `inspect.EndOfBlock` | O(1) | O(1) | The token-eating state machine `getblock()` drives, and the two exceptions that stop it |

### Signatures

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.signature(callable, *, follow_wrapped=True, globals=None, locals=None, eval_str=False, annotation_format=...)` | O(w·p), O(w·p + v) on Python 3.11 | O(w + p), O(w + p + v) on Python 3.11 | Rebuilds the parameters at each surviving `partial` layer, so a chain costs p per link. Nothing is cached, except that a function's own `__signature__` attribute is returned as it stands — reached through a bound method it is still rebuilt without the bound parameter. A class costs the search for `__init__`, `__new__` or a metaclass `__call__` as well |
| `inspect.Signature(parameters=None, *, return_annotation)` | O(p) | O(p) | Validates parameter order and rejects duplicate names |
| `Signature.from_callable(obj, *, follow_wrapped=True, ...)` | O(w·p), O(w·p + v) on Python 3.11 | O(w + p), O(w + p + v) on Python 3.11 | What `signature()` calls, with the same arguments |
| `Signature.parameters` | O(1) | O(1) | The same `mappingproxy` on every access, over the ordered mapping built with the signature |
| `Signature.return_annotation` | O(1) | O(1) | Attribute read; `Signature.empty` when absent |
| `Signature.replace(*, parameters, return_annotation)` | O(p) | O(p) | Builds a new `Signature`; the original is untouched |
| `Signature.bind(*args, **kwargs)`, `Signature.bind_partial(*args, **kwargs)` | O(p + a) | O(p + a) | a = arguments supplied; a `*args` or `**kwargs` parameter collects all of them. `bind()` raises `TypeError` on a missing required parameter, `bind_partial()` allows it |
| `Signature.format(*, max_width=None, quote_annotation_strings=True)` | O(r) | O(r) | Python 3.13+. `str(sig)` is the same work. `quote_annotation_strings` is Python 3.14+ — passing it on 3.13 raises `TypeError` |
| `Signature.empty` | O(1) | O(1) | The sentinel for "no annotation" |
| `inspect.Parameter(name, kind, *, default, annotation)` | O(1) | O(1) | Validates the name and the kind |
| `Parameter.name`, `Parameter.kind`, `Parameter.default`, `Parameter.annotation` | O(1) | O(1) | Attribute reads on an immutable object |
| `Parameter.kind.description` | O(1) | O(1) | The human-readable form of the kind, such as `'positional or keyword'` |
| `Parameter.replace(*, name, kind, default, annotation)` | O(1) | O(1) | Builds a new `Parameter` |
| `Parameter.empty` | O(1) | O(1) | The same sentinel as `Signature.empty` |
| `inspect.BoundArguments` | O(1) | O(1) | Holds the signature and the `arguments` mapping the bind produced |
| `BoundArguments.arguments` | O(1) | O(1) | The mutable mapping itself, not a copy |
| `BoundArguments.args`, `BoundArguments.kwargs` | O(p + a) | O(p + a) | Rebuilt from `arguments` on every access, variadic entries expanded |
| `BoundArguments.signature` | O(1) | O(1) | The `Signature` the bind came from |
| `BoundArguments.apply_defaults()` | O(p) | O(p) | Fills every unsupplied parameter that has a default |

### Argument specs and call binding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.getfullargspec(func)` | O(w·p), O(w·p + v) on Python 3.11 | O(w + p), O(w + p + v) on Python 3.11 | A `signature()` build with wrappers and bound arguments left alone, flattened into a tuple |
| `inspect.FullArgSpec` | O(1) | O(1) | The seven-field named tuple it returns |
| `inspect.getargs(co)` | O(p), O(p + v) on Python 3.11 | O(p), O(p + v) on Python 3.11 | Slices the argument names out of `co_varnames`, which 3.11 alone rebuilds from the code object's whole variable layout on every access |
| `inspect.Arguments` | O(1) | O(1) | The `(args, varargs, varkw)` named tuple `getargs` returns |
| `inspect.getargvalues(frame)` | O(p) from Python 3.13, O(p + v) before and on 3.11 | O(p) from Python 3.13, O(p + v) before | `getargs()` plus the frame's `f_locals`, which refreshes every local before Python 3.13 and hands back a proxy from it |
| `inspect.ArgInfo` | O(1) | O(1) | The `(args, varargs, keywords, locals)` named tuple `getargvalues` returns |
| `inspect.formatargvalues(args, varargs, varkw, locals, ...)` | O(p·r), plus O(p·v) against a frame proxy on Python 3.13+ | O(p·r) | Every bound value is `repr`'d, so `r` is the longest of them. Each name is looked up in `locals`, which is O(1) in a dict but a scan of the frame's variables in the proxy `getargvalues()` returns from Python 3.13 |
| `inspect.getcallargs(func, /, *args, **kwds)` | O(w·p + a), plus v on Python 3.11 | O(w + p + a), plus v on Python 3.11 | `getfullargspec()`, then its own binding pass. It does not see positional-only parameters, so it accepts by keyword what the call itself would reject — `Signature.bind()` does not |
| `inspect.getclosurevars(func)` | O(i + f) on Python 3.12+, O(g + f) before | O(i + g + f) on Python 3.12+, O(g + f) before | f = free variables. Python 3.12+ disassembles the **whole** code object to tell an attribute name from a global one, which needs room for the disassembler's own line and jump tables; earlier versions read `co_names` directly. Either way the closure is the cheap part |
| `inspect.ClosureVars` | O(1) | O(1) | The `(nonlocals, globals, builtins, unbound)` named tuple it returns |
| `inspect.unwrap(func, *, stop=None)` | O(w) | O(w) | Follows `__wrapped__` to the end, keeping every link to detect a cycle |

### The interpreter stack

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.currentframe()` | O(1) | O(1) | The caller's frame, or `None` where frame support is absent |
| `inspect.getlineno(frame)` | O(x) | O(1) | Reads `f_lineno`, which resolves the frame's current instruction offset against the code object's line table. A frame stopped deep inside a long function costs more than one stopped near its start |
| `inspect.getframeinfo(frame, context=1)` | O(x + F) first call for a file, then O(x + context) | O(F) | The line number alone is O(x); from Python 3.11 the column range is a second walk of the same length. Both are paid whatever `context` is, as is `getsourcefile()` — so a frame whose filename is synthetic, such as one from `exec()`, adds that function's O(M) even at `context=0`. With `context > 0` it also calls `findsource()`, so the frame's file is read once and cached |
| `inspect.getouterframes(frame, context=1)`, `inspect.getinnerframes(tb, context=1)` | O(d·(x + context)) plus one file read per distinct uncached file | O(d·(1 + context)), plus each newly cached file | One `getframeinfo()` per frame, each keeping its own slice of `context` lines; `context=0` skips the source lookup but not the position walk |
| `inspect.stack(context=1)` | O(d·(x + context)) plus one file read per distinct uncached file | O(d·(1 + context)), plus each newly cached file | `getouterframes(currentframe())` |
| `inspect.trace(context=1)` | O(d·(x + context)) plus one file read per distinct uncached file | O(d·(1 + context)), plus each newly cached file | `getinnerframes()` over the traceback being handled |
| `inspect.FrameInfo`, `inspect.Traceback` | O(1) | O(1) | The records the four above yield. `FrameInfo` is a class from Python 3.11 |
| `FrameInfo.frame`, `FrameInfo.filename`, `FrameInfo.lineno`, `FrameInfo.function`, `FrameInfo.code_context`, `FrameInfo.index`, `FrameInfo.positions` | O(1) | O(1) | Attribute reads. `positions` is Python 3.11+ |
| `Traceback.filename`, `Traceback.lineno`, `Traceback.function`, `Traceback.code_context`, `Traceback.index`, `Traceback.positions` | O(1) | O(1) | The same fields without the frame; `positions` is Python 3.11+ |

### Constants and flags

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `inspect.CO_OPTIMIZED`, `inspect.CO_NEWLOCALS`, `inspect.CO_VARARGS`, `inspect.CO_VARKEYWORDS`, `inspect.CO_NESTED`, `inspect.CO_GENERATOR`, `inspect.CO_NOFREE`, `inspect.CO_COROUTINE`, `inspect.CO_ITERABLE_COROUTINE`, `inspect.CO_ASYNC_GENERATOR`, `inspect.CO_HAS_DOCSTRING`, `inspect.CO_METHOD` | O(1) | O(1) | Bit masks for `code.co_flags`; the last two are Python 3.14+ |
| `inspect.TPFLAGS_IS_ABSTRACT` | O(1) | O(1) | The `type.__flags__` bit `isabstract()` reads |
| `inspect.GEN_CREATED`, `inspect.GEN_RUNNING`, `inspect.GEN_SUSPENDED`, `inspect.GEN_CLOSED` | O(1) | O(1) | The strings `getgeneratorstate()` returns |
| `inspect.CORO_CREATED`, `inspect.CORO_RUNNING`, `inspect.CORO_SUSPENDED`, `inspect.CORO_CLOSED` | O(1) | O(1) | The strings `getcoroutinestate()` returns |
| `inspect.AGEN_CREATED`, `inspect.AGEN_RUNNING`, `inspect.AGEN_SUSPENDED`, `inspect.AGEN_CLOSED` | O(1) | O(1) | Python 3.12+; the strings `getasyncgenstate()` returns |
| `inspect.BufferFlags` | O(1) | O(1) | Python 3.12+; an `IntFlag` of the buffer-protocol request flags |

## Predicates Read Flags

The type checks are `isinstance` calls against concrete types, so they cost nothing that grows.
The three that ask whether a *function* is a generator, coroutine or async generator do a little
more: before reading the code flag they strip `functools.partial`, `partialmethod` and bound-method
layers. Nesting plain partials does not build a chain, because each absorbs the one below it when
you construct it — so `w` is normally 1. A partial that has been given an attribute of its own is
not absorbed, and a chain of those is walked link by link.

```python
import functools
import inspect

def plain(a, b):
    return a + b

async def coro(a, b):
    return a + b

assert inspect.isfunction(plain) is True       # O(1)
assert inspect.isroutine(plain) is True        # O(1)
assert inspect.iscoroutinefunction(plain) is False
assert inspect.iscoroutinefunction(coro) is True   # O(w), w = 1

# Nesting plain partials does not nest them: each absorbs the one below
wrapped = coro
for _ in range(5):
    wrapped = functools.partial(wrapped, 1)
assert wrapped.func is coro                          # five calls, one partial
assert inspect.iscoroutinefunction(wrapped) is True  # O(w), w still 1

# Give one an attribute and it is no longer absorbed - now there is a chain
layered = coro
for index in range(5):
    layered = functools.partial(layered, 1)
    layered.tag = index
assert layered.func is not coro                      # five calls, five partials
assert inspect.iscoroutinefunction(layered) is True  # O(w), w = 5

coro(1, 2).close()
```

`markcoroutinefunction()` sets a marker instead of a code flag, which is how a callable that is not
an `async def` can still answer `True`.

```python
import inspect
import sys

if sys.version_info >= (3, 12):
    def returns_awaitable(a):
        return a

    inspect.markcoroutinefunction(returns_awaitable)  # O(1)
    assert inspect.iscoroutinefunction(returns_awaitable) is True
    assert inspect.isfunction(returns_awaitable) is True
```

## Members and the MRO

### getmembers() Runs Every Descriptor

`getmembers()` calls `dir()`, then `getattr` for each name it got back, then sorts. The sort makes
it O(m log m), but the part that actually hurts is the `getattr`: every property, cached property
and custom descriptor on the object is invoked, and whatever they cost is added to the total.
`getmembers_static()` reads the same names out of the instance and MRO dictionaries instead, so no
property or descriptor is invoked — at the price of an MRO walk in Python per name. It still calls
`dir()`, and it still calls whatever predicate you pass.

```python
import inspect
import sys

calls = []

class Config:
    @property
    def expensive(self):
        calls.append('ran')
        return sum(range(1000))

config = Config()

names = [name for name, _ in inspect.getmembers(config)]  # O(m log m) + descriptors
assert 'expensive' in names
assert calls == ['ran']  # the property was evaluated to get its value

if sys.version_info >= (3, 11):
    calls.clear()
    static = dict(inspect.getmembers_static(config))  # O(m·c + m log m), nothing runs
    assert calls == []
    assert isinstance(static['expensive'], property)  # the descriptor itself

# A predicate filters the result; it does not save the getattr
methods = inspect.getmembers(config, inspect.ismethod)  # still O(m log m)
assert all(inspect.ismethod(value) for _, value in methods)
```

### getmro() Hands Back the Tuple

`getmro()` returns `cls.__mro__` itself. There is no copy and no length-proportional work, which is
why it is O(1) however deep the hierarchy goes — and why the result must not be mutated through.

```python
import inspect

class Base: pass
class Middle(Base): pass
class Leaf(Middle): pass

mro = inspect.getmro(Leaf)          # O(1) - the existing tuple
assert mro is Leaf.__mro__
assert mro == (Leaf, Middle, Base, object)

# classify_class_attrs is the opposite: it searches the MRO once per name
attrs = {a.name: a for a in inspect.classify_class_attrs(Leaf)}  # O(m·c)
assert attrs['__init__'].defining_class is object
assert attrs['__init__'].kind == 'method'
```

### getclasstree() Is Quadratic

`getclasstree()` builds its parent-to-children map with list membership tests, so the classes you
hand it are rescanned for every base link (q below is the list's length). The returned tree is a second cost: a class is placed
under every base it reaches and drags its descendants along each time, so a lattice of classes
produces a tree far larger than the list you gave. `unique=True` stops at the first base that is
itself in `classes`, which deduplicates within the list — a class whose bases are all outside it is
still placed under each of them.

```python
import inspect

class Animal: pass
class Dog(Animal): pass
class Cat(Animal): pass

tree = inspect.getclasstree([Dog, Cat])  # O(e·q + T log T), q = classes given
assert tree[0] == (Animal, Animal.__bases__)
assert [entry[0] for entry in tree[1]] == [Cat, Dog]  # sorted by module, then name

# With two bases, a class is placed under each of them
class Hybrid(Dog, Cat):
    pass

def entries(tree):
    return sum(entries(item) if isinstance(item, list) else 1 for item in tree)

assert entries(inspect.getclasstree([Dog, Cat, Hybrid])) == 5   # Hybrid appears twice
assert entries(inspect.getclasstree([Dog, Cat, Hybrid], unique=True)) == 4

# unique=True only helps when the base is in the list too
assert entries(inspect.getclasstree([Hybrid])) == 4
assert entries(inspect.getclasstree([Hybrid], unique=True)) == 4  # still under both bases

# walktree sorts each sibling list in place - pass a list you own
siblings = [Dog, Cat]
inspect.walktree(siblings, {}, None)  # O(T log T)
assert siblings == [Cat, Dog]
```

## Docstrings Are Cleaned Every Time

`getdoc()` runs `cleandoc()` on each call, so reading the same docstring in a loop pays its length
every time — there is no cache. `cleandoc()` is linear in the text except at the front, where it
drops leading blank lines one at a time and shifts the remainder for each. What comes back is a new string whenever there was anything to
strip; a docstring that is already one clean line is returned unchanged. Where `__doc__` is `None`,
`getdoc()` first searches the MRO for an inherited one.

```python
import inspect

class Widget:
    """Summary line.

        Indented body.
    """

class Subclass(Widget):
    pass

doc = inspect.getdoc(Widget)  # O(n), n = docstring characters
assert doc == 'Summary line.\n\nIndented body.'
assert doc is not Widget.__doc__          # a fresh, cleaned string
assert inspect.getdoc(Widget) is not doc  # and a fresh one again

class Terse:
    """Nothing to strip."""

assert inspect.getdoc(Terse) is Terse.__doc__  # nothing to strip, same string back

assert Subclass.__doc__ is None
assert inspect.getdoc(Subclass) == doc    # O(c) MRO search, then O(n)

assert inspect.cleandoc('a\n    b\n      c\n') == 'a\nb\n  c'  # O(n) - the common margin goes
```

## Source Costs What Follows the Definition

Everything that returns source text unwraps the object first, then goes through `findsource()`,
which reads every line of the defining file into `linecache`. That read happens once per file; afterwards `findsource()` hands
back the cached list and takes the definition's line number off the object, so it is O(1).

`getsourcelines()` is where the remaining cost lives. It slices from the definition to the end of
the file and tokenizes until the block closes, so what it costs is the *tail* of the file below the
definition — not the file, and not the few lines it returns. The same two-line function is cheap at
the bottom of a large module and expensive at the top of one.

```python
import inspect
import os
import shutil
import tempfile
import textwrap

module = textwrap.dedent('''
    def tiny():
        return 1
''') + '\nplaceholder = 0\n' * 500

directory = tempfile.mkdtemp()
path = os.path.join(directory, 'sample.py')
with open(path, 'w', encoding='utf-8') as handle:
    handle.write(module)

import importlib.util
spec = importlib.util.spec_from_file_location('sample', path)
assert spec is not None and spec.loader is not None
sample = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sample)

lines, start = inspect.getsourcelines(sample.tiny)  # O(t) once the file is cached
assert lines == ['def tiny():\n', '    return 1\n']  # O(b) returned
assert start == 2
assert inspect.getsource(sample.tiny) == ''.join(lines)  # O(t) again - the block is not cached

# findsource() is the cached half: the whole file, and the definition's index into it
all_lines, index = inspect.findsource(sample.tiny)  # O(1) after the first call
assert all_lines[index] == 'def tiny():\n'
assert len(all_lines) > 500

shutil.rmtree(directory)
```

`getsourcefile()` reads no file contents at all: one attribute read and one stat. Use it when the
path is all you need. It returns `None` for a C extension module, and `getfile()` raises for a
module built into the interpreter, which has no file at all.

```python
import inspect
import collections

assert inspect.getsourcefile(inspect.getdoc).endswith('inspect.py')   # O(1)
assert inspect.getfile(collections).endswith('collections/__init__.py')  # O(1)
assert inspect.getmodulename('/tmp/thing.py') == 'thing'              # O(1)

# A module with no Python source behind it has no file to point at
import sys

assert 'sys' in sys.builtin_module_names
try:
    inspect.getfile(sys)  # O(1)
except TypeError as error:
    assert 'built-in module' in str(error)
else:
    raise AssertionError('a file was produced for a built-in module')
```

### getmodule() Can Scan sys.modules

An object carrying `__module__` — a class, a function, a method — resolves through one
`sys.modules` lookup. A code object or a frame has no `__module__`, so the call for one builds a
file-to-module map over every loaded module and caches it in `inspect.modulesbyfile`. Only matches
go into that map, so a code object whose file belongs to no loaded module repeats the whole scan
every time you ask.

```python
import inspect

assert inspect.getmodule(inspect.Signature) is inspect  # O(1) via __module__

def local():
    return inspect.currentframe()

frame = local()
assert inspect.getmodule(frame.f_code) is not None  # O(M) the first time, then cached
assert inspect.getmodule(frame) is inspect.getmodule(frame.f_code)
del frame
```

## Signatures Are Built, Not Cached

`signature()` constructs a new `Signature` on every call — there is no cache behind it, so calling it
again in a loop rebuilds the whole thing — and rebuilds the parameter list once per surviving
`partial` layer, so a wrapper chain multiplies rather than adds. The exception is a function
carrying an explicit `__signature__`: that object is handed back as it stands. Reaching the same attribute through a
bound method is not free, because the bound parameter still has to be removed from it. Within one `Signature`, `.parameters` is the same
`mappingproxy` every time, so reaching it costs nothing; walking its entries is still O(p).

```python
import inspect

def handler(request, *, timeout: float = 1.0, **options) -> bool:
    return True

sig = inspect.signature(handler)  # O(w + p)
assert sig is not inspect.signature(handler)   # no cache
assert sig == inspect.signature(handler)       # but equal

assert sig.parameters is sig.parameters        # O(1), the same mappingproxy
assert list(sig.parameters) == ['request', 'timeout', 'options']  # O(p) to walk
assert sig.return_annotation is bool
assert sig.parameters['timeout'].default == 1.0
assert sig.parameters['timeout'].kind is inspect.Parameter.KEYWORD_ONLY
assert sig.parameters['timeout'].kind.description == 'keyword-only'
assert sig.parameters['request'].annotation is inspect.Parameter.empty

# replace() builds a new signature; the original is untouched
narrowed = sig.replace(return_annotation=int)  # O(p)
assert narrowed.return_annotation is int
assert sig.return_annotation is bool

# An explicit __signature__ short-circuits the build and comes back as it is
handler.__signature__ = narrowed
assert inspect.signature(handler) is narrowed  # O(1)
del handler.__signature__
```

`follow_wrapped=True` walks the `__wrapped__` chain that `functools.wraps` leaves behind, which is
why a decorated function reports the signature a caller actually needs.

```python
import functools
import inspect

def log(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@log
def fetch(url, timeout=5):
    return url

assert str(inspect.signature(fetch)) == '(url, timeout=5)'          # O(w + p)
assert str(inspect.signature(fetch, follow_wrapped=False)) == '(*args, **kwargs)'
assert inspect.unwrap(fetch).__name__ == 'fetch'                    # O(w)
```

### Binding Arguments

`bind()` applies the interpreter's own matching rules and stores the result in
`BoundArguments.arguments`. That mapping is the object itself; `.args` and `.kwargs` are rebuilt
from it each time you read them.

```python
import inspect

def render(template, *rows, width=80, **attrs):
    return template

sig = inspect.signature(render)
bound = sig.bind('report', 'a', 'b', color='red')  # O(p + a)

assert bound.arguments is bound.arguments   # O(1), the mapping itself
assert bound.args is not bound.args         # O(p), rebuilt each access
assert bound.args == ('report', 'a', 'b')
assert bound.kwargs == {'color': 'red'}
assert bound.signature is sig
assert 'width' not in bound.arguments

bound.apply_defaults()                      # O(p)
assert bound.arguments['width'] == 80

# bind_partial tolerates what bind rejects
assert sig.bind_partial().arguments == {}
try:
    sig.bind()
except TypeError as error:
    assert 'template' in str(error)
else:
    raise AssertionError('a missing required argument was accepted')
```

`getcallargs()` answers a similar question as a flat dict, and `getfullargspec()` gives the older
tuple view. Both cost a signature build. Neither sees positional-only parameters — `getfullargspec()`
folds them in with the rest — so `getcallargs()` will bind by keyword what calling the function
would reject. Use `bind()` when the answer has to match the interpreter.

```python
import inspect

def render(template, *rows, width=80, **attrs):
    return template

assert inspect.getcallargs(render, 'report', 'a') == {   # O(p + a)
    'template': 'report', 'rows': ('a',), 'width': 80, 'attrs': {},
}

# Positional-only parameters are folded into `args`, and the gap shows
def positional_only(alpha, /, beta):
    return alpha

assert inspect.getcallargs(positional_only, alpha=1, beta=2) == {'alpha': 1, 'beta': 2}
try:
    inspect.signature(positional_only).bind(alpha=1, beta=2)  # O(p + a)
except TypeError as error:
    assert 'positional' in str(error)
else:
    raise AssertionError('bind() accepted a positional-only keyword')

spec = inspect.getfullargspec(render)  # O(p)
assert spec.args == ['template']
assert spec.varargs == 'rows'
assert spec.varkw == 'attrs'
assert spec.kwonlyargs == ['width']
assert spec.kwonlydefaults == {'width': 80}
```

### Closure Variables Cost the Bytecode

`getclosurevars()` reads the nonlocals straight out of the closure cells. Sorting the remaining
names into globals, builtins and unresolved ones is the expensive half: from Python 3.12 it
disassembles the entire code object, so the cost is the function body rather than the closure.
Earlier versions walk `co_names`, which is only the names the body mentions.

```python
import inspect

def outer():
    captured = 42

    def inner():
        return captured + len('x')

    return inner

variables = inspect.getclosurevars(outer())  # O(i) from 3.12, O(g) before
assert variables.nonlocals == {'captured': 42}
assert variables.globals == {}
assert variables.builtins == {'len': len}
assert variables.unbound == set()
```

## Walking the Stack

`currentframe()` is one attribute away from free. `stack()` is not, for two reasons. Each record
carries a line of source context by default, which sends that frame through `findsource()` — a dict
lookup once the file is in `linecache`, but a file read the first time through unfamiliar code.
Passing `context=0` skips that. What it does not skip is resolving each frame's position: reading
`f_lineno` walks the code object's line table to the current instruction, and from Python 3.11 the
column range walks it again. Nor does it skip `getsourcefile()`, which for a frame with no file on
disk falls through to a `sys.modules` scan. So a deep stack in long functions costs something per
frame either way.

```python
import inspect

def innermost():
    default = inspect.stack()      # O(d·(x + 1)) - plus a source lookup per frame
    lean = inspect.stack(0)        # O(d·x) - the position walk remains
    return default, lean

def middle():
    return innermost()

default, lean = middle()

assert [frame.function for frame in default[:3]] == ['innermost', 'middle', '<module>']
assert default[0].code_context is not None   # a line of source was read
assert lean[0].code_context is None          # context=0 skipped it
assert lean[0].index is None
assert len(default) == len(lean)

frame = inspect.currentframe()   # O(1)
assert inspect.getlineno(frame) == frame.f_lineno  # O(x), both walk the line table
assert inspect.getframeinfo(frame, 0).function == '<module>'  # O(x), no source read
del frame
```

`trace()` is the same shape over the traceback currently being handled, innermost frame last.

```python
import inspect

def fails():
    raise ValueError('boom')

try:
    fails()
except ValueError:
    frames = inspect.trace(0)   # O(d·x), no source lookup or context lines
    assert [frame.function for frame in frames] == ['<module>', 'fails']
    assert frames[-1].lineno > 0
else:
    raise AssertionError('the call did not raise')
```

### Reading a Caller's Arguments

`getargvalues()` names the arguments from the code object and hands back the frame's locals. From
Python 3.13 that is a live proxy rather than a refreshed dict, so obtaining it is O(1) rather than
O(v) — at the cost of every later lookup scanning the frame's variables, which is what
`formatargvalues()` then does once per argument.

```python
import inspect

def inspected(alpha, beta=2, *extra, **options):
    frame = inspect.currentframe()
    assert frame is not None
    info = inspect.getargvalues(frame)   # O(p), O(p + v) before 3.13
    rendered = inspect.formatargvalues(*info)  # O(p·r), plus O(p·v) from 3.13
    del frame
    return info, rendered

info, rendered = inspected(1, 2, 3, flag=True)

assert info.args == ['alpha', 'beta']
assert info.varargs == 'extra'
assert info.keywords == 'options'
assert info.locals['alpha'] == 1
assert rendered == "(alpha=1, beta=2, *extra=(3,), **options={'flag': True})"
```

## Generator and Coroutine State

The state functions read flags off the generator and are O(1). The `*locals()` functions return the
suspended frame's locals, which is where a debugger gets its view without resuming anything.

```python
import inspect

def counter():
    total = 0
    for step in range(3):
        total += step
        yield total

generator = counter()
assert inspect.getgeneratorstate(generator) == inspect.GEN_CREATED  # O(1)

next(generator)
assert inspect.getgeneratorstate(generator) == inspect.GEN_SUSPENDED
assert inspect.getgeneratorlocals(generator) == {'total': 0, 'step': 0}  # O(1), O(v) before 3.13

generator.close()
assert inspect.getgeneratorstate(generator) == inspect.GEN_CLOSED
assert inspect.getgeneratorlocals(generator) == {}
```

## Common Patterns

### Listing a Module's Public Functions

```python
import inspect
import textwrap

functions = inspect.getmembers(textwrap, inspect.isfunction)  # O(m log m)
names = [name for name, _ in functions if not name.startswith('_')]

assert 'dedent' in names and 'wrap' in names
assert names == sorted(names)  # getmembers sorts by name
```

### Checking a Callback Against a Protocol

`signature()` has no cache, so a checker that calls it per event rebuilds the signature every time.
Build it once and keep only the `bind()`, which is O(p + a).

```python
import inspect

def checker(callback):
    """A predicate that reuses one signature: O(w·p) once."""
    signature = inspect.signature(callback)  # O(w·p), built once

    def expects(*args, **kwargs):
        try:
            signature.bind(*args, **kwargs)  # O(p + a) per call
        except TypeError:
            return False
        return True

    return expects

def on_event(name, payload=None):
    return name

expects = checker(on_event)

assert expects('click') is True
assert expects('click', payload={}) is True
assert expects() is False
assert expects('click', {}, 'extra') is False
```

### Recording Where a Call Came From

```python
import inspect

def caller_location(depth=1):
    """The filename and line of the frame `depth` levels up: O(depth + x)."""
    frame = inspect.currentframe()   # O(1) - this function's own frame
    try:
        # One step to leave this function, then `depth` more - O(depth)
        for _ in range(depth + 1):
            assert frame is not None
            frame = frame.f_back
        assert frame is not None
        return frame.f_code.co_filename, frame.f_lineno  # O(x) to resolve the line
    finally:
        del frame

def helper():
    return caller_location()

filename, lineno = helper()
assert filename.endswith('.py')
assert lineno > 0
```

## Performance Best Practices

✅ **Do**:

- Cache a `Signature` when the same callable is inspected repeatedly; `signature()` builds a new one
  every call, and `bind()` against a held one is O(p + a)
- Pass `context=0` to `stack()`, `trace()`, `getouterframes()` and `getframeinfo()` when you only
  need frame data — it removes the per-frame source read, though not the position walk or the
  filename lookup
- Walk `frame.f_back` yourself for a fixed number of frames instead of calling `stack()` and
  indexing the result, and read `f_lineno` only on the frame you wanted
- Use `getsourcefile()` when a path is all you need; it never reads the file
- Prefer `getmembers_static()` where running properties would be wrong, and accept the MRO walk
- Hold on to a `getdoc()` result rather than calling it again

❌ **Avoid**:

- `getmembers()` on an object whose properties are expensive or have side effects — every one of
  them runs
- `getclasstree()` on a large class list; its cost is quadratic in the classes you pass
- `getsource()` in a loop: `findsource()` is cached, but the slice and the tokenize pass are not
- `getclosurevars()` on a long function when you only wanted the closure — `func.__closure__` and
  `co_freevars` are O(closure)
- Keeping a frame or `FrameInfo` alive past the function that produced it; `del` it instead

## Version Notes

- **Python 3.11 only**: `code.co_varnames` is rebuilt from the code object's variable layout on
  every access rather than cached, so anything reading it pays the function's locals as well as its
  parameters — `getargs()` and `getargvalues()` most visibly, `signature()` and `getfullargspec()`
  through the same attribute. 3.10 and 3.12 onwards cache it
- **Python 3.11+**: `FrameInfo` is a class rather than a named tuple, and `FrameInfo.positions` and
  `Traceback.positions` carry the column range — which `getframeinfo()` fills by walking the code
  object's position table to the frame's current instruction, at every `context`. That is a second
  walk beside the line-table one `f_lineno` has always done. `getmembers_static()` and
  `ismethodwrapper()` were added
- **Python 3.12+**: Added `markcoroutinefunction()`, `BufferFlags`, `getasyncgenstate()`,
  `getasyncgenlocals()` and the `AGEN_*` states. `getclosurevars()` began disassembling the code
  object instead of reading `co_names`, which moved its cost from the names a body mentions to the
  body itself
- **Python 3.13+**: `findsource()` takes a class's line number from `__firstlineno__`, so it is O(1)
  on a cached file like every other object. Python 3.12 and earlier parse the whole file's AST on
  every call for a class, and walk backwards from a code object's first line to its definition.
  `frame.f_locals` became a live proxy, so `getargvalues()` and `getgeneratorlocals()` no longer
  refresh the frame's variables — but each lookup through the proxy now scans them, which
  `formatargvalues()` pays per argument. `Signature.format()` was added, taking `max_width`
  only; its `quote_annotation_strings` argument arrived in 3.14
- **Python 3.13+**: `iscoroutinefunction()` and its two siblings began stripping `partialmethod`
  as well as `partial`, and `ismethoddescriptor()` began excluding a type that defines `__delete__`
- **Python 3.13 and 3.12.10**: `getattr_static()` began building a weak reference per MRO entry
  while looking for a shadowed `__dict__`, so its auxiliary space follows the hierarchy rather than
  staying constant. This one moved in a patch release, not a minor one
- **Python 3.14+**: Added `ispackage()`, `CO_METHOD` and `CO_HAS_DOCSTRING`. `get_annotations()`
  gained a `format` argument and stopped copying a class's whole `__dict__` to reach its
  annotations; `signature()` and `Signature.from_callable()` gained an `annotation_format` one
- **All Python 3**: `getmro()` returns the class's own `__mro__` tuple, and `BoundArguments.arguments`
  is the live mapping — neither is a defensive copy

## Related Modules

- **[dis](dis.md)** - disassembly; `getclosurevars()` is a caller of it
- **[types](types.md)** - the concrete types the `is*()` predicates test against
- **[traceback](traceback.md)** - formatting the frames `trace()` returns
- **[functools](functools.md)** - `wraps()` and `partial()`, the wrappers `signature()` unwinds
- **[linecache](linecache.md)** - the file cache every source function reads through
