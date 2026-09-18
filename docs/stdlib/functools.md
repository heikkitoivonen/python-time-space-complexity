# functools Module Complexity

The `functools` module wraps callables: it memoizes them, binds arguments to them, copies their
metadata, folds them over an iterable and dispatches on an argument's type. The work is per call:
`reduce` walks its iterable, a dispatch miss walks the registry, and nothing else touches more than
the arguments it is handed. Memory is what an object was given to keep, plus the caches, which
grow with the distinct calls made through them.

`f` is the cost of one call of the user's function, whichever is wrapped, folded or compared.
`a` and `m` are the positional and keyword arguments supplied to one call, `p` and `q` the
positional and keyword bindings a `partial` stores. `n` is the entries a cache holds, the items
`reduce` folds or the elements a sort compares. `k` is the implementations registered on a generic function, `t` the distinct
argument types it has dispatched, and `L` the classes linearised on a dispatch miss: the argument
class's MRO plus the MROs of the registered ABCs that recognise the class without appearing in it,
and of those ABCs' subclasses that recognise it. `P` is the paths through that inheritance graph,
one per way each of the L classes can be reached, which is L unless a base is inherited more than
once. `w` is the
names in `assigned` when a wrapper is updated, and `u` the names in `updated` plus the entries
across the mappings they name. Hashing and comparing one argument, one attribute lookup and one
subclass check are treated as O(1).

## Complexity Reference

### lru_cache

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.lru_cache(maxsize=128, typed=False)` | O(1) to build, O(w + u) to apply | O(min(n, maxsize)) entries | Applying it copies the function's metadata as `update_wrapper` does; the cache then holds at most `maxsize` entries, every entry with `maxsize=None` and none with `maxsize=0`, each holding its key and result; `typed=True` keys `3` and `3.0` separately |
| `functools.cache(user_function)` | O(w + u) | O(n) entries | `lru_cache(maxsize=None)`: nothing is ever evicted |
| Calling a cached function, hit | O(a + m) | O(a + m) | The key is built from every argument and hashed before the lookup, which is then O(1) avg; keyword order is part of the key, and an unhashable argument raises `TypeError` before the function runs; with `maxsize=0` no key is built and the function is simply called |
| Calling a cached function, miss | O(a + m + f) | O(a + m) | Stores the key and the result; with a positive `maxsize` the least recently used entry is evicted in O(1) |
| `cache_info()` | O(1) | O(1) | A fresh `CacheInfo` tuple of hits, misses, maxsize and currsize |
| `cache_clear()` | O(n) | O(1) | Drops every entry and zeroes the counters |
| `cache_parameters()` | O(1) | O(1) | A fresh dict of `maxsize` and `typed` |
| `__wrapped__` | O(1) | O(1) | The undecorated function |

### cached_property

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.cached_property(func)` | O(1) | O(1) | Builds the descriptor |
| First access to the attribute | O(f) | O(1) | Stores the value in the instance `__dict__`, so an instance without one, such as a `__slots__` class, raises `TypeError` |
| Later access | O(1) | O(1) | An ordinary instance attribute; `del` it to recompute |

### partial

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.partial(func, /, *args, **keywords)` | O(p + q) | O(p + q) | Copies the bindings; wrapping another `partial` merges the two sets rather than nesting, unless the inner one has a `__dict__`, which setting an attribute on it or reading `vars()` of it creates |
| `partial.func`, `partial.args`, `partial.keywords` | O(1) | O(1) | The stored callable, tuple and dict themselves; `keywords` is live, so mutating it changes later calls |
| Calling a `partial` | O(p + q + a + m + f) | O(p + q + a + m) | The stored and supplied arguments are joined into one call; stored keywords are copied and merged on every call |
| `functools.Placeholder` | O(1) | O(1) | Python 3.14+; a call's positional arguments fill the placeholders left to right within the same bound, and a call supplying fewer raises `TypeError` |
| `functools.partialmethod(func, /, *args, **keywords)` | O(p + q) | O(p + q) | Same storage and flattening; each access through an instance builds a new `partial` around the bound method, so `obj.method` costs O(p + q) before the call, or a fresh wrapper function in O(1) when `func` has no `__get__` or its `__get__` hands back `func` itself |

### update_wrapper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.update_wrapper(wrapper, wrapped, assigned=WRAPPER_ASSIGNMENTS, updated=WRAPPER_UPDATES)` | O(w + u) | O(w + u) | Each name in `assigned` is fetched and set, a missing one skipped but still looked up; each mapping `updated` names is fetched and every entry in it copied into the wrapper's |
| `functools.wraps(wrapped, assigned=WRAPPER_ASSIGNMENTS, updated=WRAPPER_UPDATES)` | O(1) to build, O(w + u) when applied | O(w + u) | A `partial` of `update_wrapper` |
| `functools.WRAPPER_ASSIGNMENTS`, `functools.WRAPPER_UPDATES` | O(1) | O(1) | The default name tuples: a fixed handful of metadata names, and `__dict__` |

### reduce

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.reduce(function, iterable[, initial])` | O(n·f) | O(1) auxiliary, plus the accumulator | `function` runs n-1 times, n with `initial`; the accumulator is whatever `function` returns and is fed back in, so `+` on strings makes the fold O(n²) and a product of integers, whose width keeps growing, super-linear |

### cmp_to_key and total_ordering

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.cmp_to_key(func)` | O(1) | O(1) | Returns a key class; wrapping one element is O(1), and every comparison then calls `func`, so a sort pays O(n log n) calls of f rather than n key computations |
| `functools.total_ordering(cls)` | O(1) | O(1) | Fills in the missing comparison methods from the one defined and `__eq__`; a derived comparison calls up to two of them |

### singledispatch

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `functools.singledispatch(func)` | O(w + u) | O(w + u) | Registers `func` for `object` and copies its metadata as `update_wrapper` does |
| `singledispatch.register(cls, func=None)` | O(t), plus one entry per union member | O(1) per entry | One registry entry, or one per member of a union type (Python 3.11+), and the t cached entries are cleared; the annotation form evaluates the function's annotations first |
| `singledispatch.dispatch(cls)` | O(1) avg hit, O(k + s + P·L²) miss | O(t), plus O(s + L²) during a miss | An exactly registered class is found without a search; any other miss checks every registration against the class, checks the s direct subclasses of the registered ABCs that recognise it, and linearises its MRO with those ABCs in Python, revisiting a base once per path to it, then caches the result weakly per class; once an ABC is registered on its own, not as a union member, an `ABCMeta.register()` call anywhere in the process that adds a virtual subclass invalidates the cache, which is cleared on the next dispatch |
| Calling a generic function | O(a + m + f) after the first call per type | O(a + m) | Forwards the arguments to the implementation for the class of the first positional one; a call without one raises `TypeError` |
| `singledispatch.registry` | O(1) | O(1) | A read-only live view of the registry, not a copy |
| `functools.singledispatchmethod(func)` | O(w + u) | O(w + u) | Wraps a `singledispatch` of `func` |
| `singledispatchmethod.register(cls, method=None)` | O(t), plus one entry per union member | O(1) per entry | The wrapped generic function's `register()` |
| Accessing `obj.method` | O(1) | O(1) | Python 3.14+; before 3.14 each access builds a function and copies the implementation's metadata, O(w + u) |
| Calling `obj.method(arg, ...)` | O(a + m + f) after the first call per type | O(a + m) | After the access priced above: dispatches on the argument after `self`, binds the implementation and forwards the arguments |

## Memoization

### Memoizing Recursion

Each distinct argument is computed once. The recursion still costs a call per level, so
`fibonacci(n)` makes O(n) calls, where the same function without the cache makes O(2ⁿ).

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)  # O(1) per hit

assert fibonacci(30) == 832040                  # O(n) calls, one miss per distinct n
info = fibonacci.cache_info()                   # O(1)
assert info.misses == 31                        # n from 0 to 30
assert info.hits == 28

fibonacci.cache_clear()                         # O(n)
assert fibonacci.cache_info().currsize == 0
```

### What a Call Key Costs

A hit is not free. The key is built from every positional and keyword argument and hashed before
the dictionary is consulted, so a call with many arguments pays for all of them whether or not
the result is cached.

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def combine(*args, **kwargs):
    return len(args) + len(kwargs)

combine(1, 2, x=3)                            # miss: O(a + m + f)
combine(1, 2, x=3)                            # hit: O(a + m) to build and hash the key
assert combine.cache_info().hits == 1

# Keyword order is part of the key, so these are two entries
combine(a=1, b=2)
combine(b=2, a=1)
assert combine.cache_info().currsize == 3

# An unhashable argument fails before the function runs
try:
    combine([1, 2])
except TypeError as error:
    assert 'unhashable' in str(error)
else:
    raise AssertionError('a list was accepted as a cache key')

@lru_cache(typed=True)
def scale(x, factor):
    return x * factor

assert scale(4, 1) == scale(4.0, 1) == 4
assert scale.cache_info().currsize == 2      # 4 and 4.0 are separate entries under typed=True
```

### Bounding the Cache

`maxsize` picks one of three modes. A positive value evicts the least recently used entry once
the cache is full, `None` keeps every entry until `cache_clear()` or the function itself goes away,
and `0` keeps none.

```python
from functools import cache, lru_cache

@lru_cache(maxsize=2)
def square(n):
    return n * n

square(1)
square(2)
square(1)                                     # 1 is now the most recently used
square(3)                                     # evicts 2, the least recently used - O(1)
assert square.cache_info().currsize == 2
square(2)                                     # a miss again
assert square.cache_info().misses == 4

@cache                                        # lru_cache(maxsize=None): O(n), never evicts
def cube(n):
    return n ** 3

for n in range(1000):
    cube(n)
assert cube.cache_info() == (0, 1000, None, 1000)
assert cube.cache_parameters() == {'maxsize': None, 'typed': False}  # O(1)
assert cube.__wrapped__(3) == 27              # O(1): the undecorated function

@lru_cache(maxsize=0)                         # stores nothing: every call is a miss
def identity(n):
    return n

identity(1)
identity(1)
assert identity.cache_info() == (0, 2, 0, 0)
```

### Caching Methods

On a method, `self` is part of every key, so the cache keeps each instance alive until its entries
go. A class with many or large instances pays that in memory for as long as the cache lasts.

```python
import gc
import weakref
from functools import lru_cache

class Report:
    @lru_cache(maxsize=None)
    def total(self):
        return 42

report = Report()
ref = weakref.ref(report)
assert report.total() == 42       # the key is (self,), so the entry holds the instance
del report
gc.collect()
assert ref() is not None          # still alive: the cache holds it

Report.total.cache_clear()        # O(n)
gc.collect()
assert ref() is None
```

### cached_property

The value is computed on the first access and stored as an ordinary attribute on the instance, so
every later access is a plain attribute lookup with no key to build. The instance needs a
`__dict__`.

```python
from functools import cached_property

class Dataset:
    def __init__(self, values):
        self.values = values
        self.computations = 0

    @cached_property
    def total(self):
        self.computations += 1
        return sum(self.values)   # O(f), once per instance

data = Dataset(range(1000))
assert data.total == 499500       # first access: computes and stores in __dict__
assert data.total == 499500       # O(1): an ordinary attribute now
assert data.computations == 1
assert 'total' in vars(data)

del data.total                    # dropping the attribute recomputes on the next access
assert data.total == 499500
assert data.computations == 2

class Slotted:
    __slots__ = ('values',)

    @cached_property
    def total(self):
        return 0

try:
    Slotted().total
except TypeError as error:
    assert '__dict__' in str(error)
else:
    raise AssertionError('a cached_property was stored without a __dict__')
```

## Partial Objects

### Binding Arguments

Building a `partial` copies its bindings once; every call then joins them with the call's own
arguments before the function runs. Wrapping a `partial` in another merges the bindings instead
of stacking a second call.

```python
from functools import partial

def power(base, exponent, *, modulus=None):
    result = base ** exponent
    return result if modulus is None else result % modulus

square = partial(power, exponent=2)           # O(p + q): stores one keyword binding
assert square.func is power                   # O(1)
assert square.args == ()
assert square.keywords == {'exponent': 2}
assert square(7) == 49                        # O(p + q + a + m) to assemble the call, then f

# Wrapping a partial merges the bindings instead of nesting a second call
square_mod_10 = partial(square, modulus=10)
assert square_mod_10.func is power
assert square_mod_10.keywords == {'exponent': 2, 'modulus': 10}
assert square_mod_10(7) == 9

# keywords is the live dict: a change reaches later calls
square.keywords['exponent'] = 3
assert square(2) == 8
```

### Placeholders

`Placeholder` (Python 3.14+) reserves a positional slot. It is stored like any other binding, and a
call's positional arguments fill the reserved slots left to right before any are appended.

```python
import sys
from functools import partial

if sys.version_info >= (3, 14):
    from functools import Placeholder

    def divide(numerator, denominator):
        return numerator / denominator

    halve = partial(divide, Placeholder, 2)   # O(p): the placeholder is one stored binding
    assert halve.args == (Placeholder, 2)
    assert halve(10) == 5.0                   # the call's first argument fills the slot

    try:
        halve()
    except TypeError as error:
        assert 'missing positional arguments' in str(error)
    else:
        raise AssertionError('a placeholder was left unfilled')
```

### partialmethod

A `partialmethod` stores its bindings once, at class creation. Reading it through an instance
builds a fresh `partial` around the bound method every time, so bind once outside a loop rather
than reading the attribute on every iteration. Only a `func` whose `__get__` yields nothing new,
such as a callable instance without one, escapes this: it gets a wrapper function that defers the
bindings to the call.

```python
from functools import partial, partialmethod

class Cell:
    def __init__(self):
        self.state = 'off'

    def set_state(self, state):
        self.state = state

    turn_on = partialmethod(set_state, 'on')    # O(p + q), once
    turn_off = partialmethod(set_state, 'off')

cell = Cell()
bound = cell.turn_on                            # O(p + q): a new partial on every access
assert isinstance(bound, partial)
assert bound is not cell.turn_on
bound()
assert cell.state == 'on'
cell.turn_off()
assert cell.state == 'off'
```

## Wrapping Functions

`update_wrapper()` copies a fixed handful of names and then the wrapped function's whole
`__dict__`, so a decorator costs whatever the function it wraps carries. `wraps()` is the same
call, deferred until the decorator applies it.

```python
from functools import WRAPPER_ASSIGNMENTS, WRAPPER_UPDATES, update_wrapper, wraps

def logged(func):
    @wraps(func)                            # O(w + u) when applied
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

def add(a, b):
    """Add two numbers."""
    return a + b

add.registered = True                       # one entry in add.__dict__, copied by the wrap

logged_add = logged(add)
assert logged_add.__name__ == 'add'
assert logged_add.__doc__ == 'Add two numbers.'
assert logged_add.registered is True
assert logged_add.__wrapped__ is add        # O(1): a reference, set last
assert '__name__' in WRAPPER_ASSIGNMENTS
assert WRAPPER_UPDATES == ('__dict__',)

def target():
    pass

update_wrapper(target, add, assigned=('__doc__',), updated=())  # w = 1, u = 0
assert target.__doc__ == 'Add two numbers.'
assert target.__name__ == 'target'
assert not hasattr(target, 'registered')
```

## Folding With reduce

`reduce()` walks the iterable once and calls the function once per step. Its cost is the
function's, and the accumulator is whatever the function returns: a function that copies the
accumulated value to extend it, as `+` on a string or list does, pays for the whole of it every
step.

```python
import operator
from functools import reduce

data = [1, 2, 3, 4, 5]

assert reduce(operator.add, data) == 15                       # O(n·f): n-1 calls
assert reduce(operator.add, [], 0) == 0                        # initial: the empty fold's result
assert reduce(lambda acc, item: f'({acc}-{item})', ['1', '2', '3']) == '((1-2)-3)'

try:
    reduce(operator.add, [])
except TypeError as error:
    assert 'empty' in str(error)
else:
    raise AssertionError('an empty fold without initial returned')

# Concatenation copies everything accumulated so far on each step: O(n²)
joined = reduce(operator.add, ['x'] * 1000)
assert len(joined) == 1000

# A product widens too: each multiplication is dearer than the last
product = reduce(operator.mul, range(1, 1001))
assert product.bit_length() > 8000

# max keeps the accumulator to one of the inputs, so the fold stays O(n)
assert reduce(max, data) == 5
```

## Comparison Helpers

### cmp_to_key

The wrapper defers the work to the comparisons. `sorted(key=cmp_to_key(f))` wraps each element in
O(1) and then calls `f` on every comparison, where a `key=` function runs once per element and the
comparisons that follow are on the keys alone.

```python
from functools import cmp_to_key

comparisons = []

def compare(left, right):
    comparisons.append((left, right))
    return (left > right) - (left < right)

data = [5, 3, 8, 1, 9, 2, 7, 4, 6, 0]
assert sorted(data, key=cmp_to_key(compare)) == list(range(10))  # O(n log n) calls of compare
assert len(comparisons) > len(data)                              # more calls than elements

key_calls = []

def key(value):
    key_calls.append(value)
    return value

assert sorted(data, key=key) == list(range(10))  # O(n) key calls, then O(n log n) comparisons
assert len(key_calls) == len(data)
```

### total_ordering

The decorator fills in the missing comparison methods once, at class creation. Each derived
comparison is expressed through the method you wrote and `__eq__`, so it can cost two calls
where a hand-written one costs one.

```python
from functools import total_ordering

calls = []

@total_ordering
class Version:
    def __init__(self, number):
        self.number = number

    def __eq__(self, other):
        calls.append('eq')
        return self.number == other.number

    def __lt__(self, other):
        calls.append('lt')
        return self.number < other.number

assert Version(1) < Version(2)                  # the method you wrote: one call
assert calls == ['lt']

calls.clear()
assert Version(2) > Version(1)                  # derived: not __lt__, then __ne__ - two calls
assert calls == ['lt', 'eq']

calls.clear()
assert Version(1) >= Version(1)                 # derived as not __lt__: one call
assert calls == ['lt']
```

## Single Dispatch

### The Dispatch Cache

The first call for an argument type is a miss: every registration is checked against the class
and its MRO is linearised with the registered ABCs that recognise it. The result is cached per
class, so later calls are one dictionary lookup, until the next `register()` clears the cache.

```python
from collections.abc import Sized
from functools import singledispatch

@singledispatch
def describe(value):
    return 'object'

@describe.register(int)                        # O(t): one entry, and the cache is cleared
def _(value):
    return 'int'

@describe.register                             # the annotation form
def _(value: list):
    return 'list'

assert describe(3) == 'int'                    # int is registered: found without a search
assert describe(True) == 'int'                 # miss for bool: O(k + s + P·L²), its MRO reaches int
assert describe(True) == 'int'                 # hit: O(1) avg
assert describe([1]) == 'list'
assert describe('text') == 'object'
assert describe.dispatch(bool) is describe.dispatch(int)
registry = describe.registry                   # O(1): a live read-only view, not a copy
assert set(registry) == {object, int, list}    # O(k) to materialise

@describe.register(Sized)                      # an ABC: from now on a new virtual subclass
def _(value):                                  # registered on any ABC invalidates this cache
    return 'sized'

assert describe('text') == 'sized'             # str is not a subclass, but Sized recognises it
assert describe(3) == 'int'                    # an exact registration needs no linearisation
```

### singledispatchmethod

The method form dispatches on the first argument after `self`, then binds the implementation it
found. Registering on it registers on the wrapped generic function, with the same cache.

```python
from functools import singledispatchmethod

class Formatter:
    @singledispatchmethod
    def render(self, value):
        return repr(value)

    @render.register
    def _(self, value: int):
        return f'{value:+d}'

formatter = Formatter()
assert formatter.render(3) == '+3'         # dispatch on value, then f
assert formatter.render('x') == "'x'"
assert formatter.render(True) == '+1'      # bool dispatches to the int implementation
```

## Common Patterns

### Binding a Callback Once

```python
from functools import partial

def scale(value, factor):
    return value * factor

doubler = partial(scale, factor=2)               # O(p + q), once
assert list(map(doubler, range(5))) == [0, 2, 4, 6, 8]  # O(p + q + a + m + f) per element
```

## Performance Best Practices

✅ **Do**:

- Register every implementation before the first call: each `register()` clears the dispatch cache, and the first call per type then pays the miss again
- Give `lru_cache` a `maxsize` that fits the working set; `maxsize=None` holds every distinct call until something clears it
- Reach for `cached_property` when the value is per instance: one attribute store, no key to build and hash
- Prefer `key=` over `cmp_to_key()` when a key function exists: n key calls instead of O(n log n) comparison calls

❌ **Avoid**:

- `lru_cache` on a method of a class with many or large instances: `self` is in every key, so the cache keeps them alive
- `reduce()` with a function that rebuilds a growing accumulator, such as `+` on strings or lists: every step copies it, and `''.join()` or `extend()` does the same work once
- Reading a `partialmethod` of an ordinary method inside a loop: every access builds a new `partial`
- Registering an ABC on a generic function that is called often: every new `ABCMeta.register()` anywhere in the process then invalidates its cache

## Version Notes

- **Python 3.11+**: `register()` accepts a union type and adds one registry entry per member
- **Python 3.12+**: `cached_property` no longer takes a lock around the first computation, so instances computed on different threads no longer serialise on one per-property lock
- **Python 3.13+**: A `partial` stored as a class attribute stops being a plain attribute: 3.13 warns with `FutureWarning` when it is read through an instance, and 3.14 binds it as a method, passing the instance first
- **Python 3.14+**: `Placeholder` is added; `reduce()` accepts `initial` as a keyword; reading a `singledispatchmethod` through an instance is O(1) instead of a metadata copy
- **All Python 3**: `register()` clears the whole dispatch cache, not one type's entry

## Related Modules

- **[operator](operator.md)** - `itemgetter` and `attrgetter` build key functions that run once per element
- **[itertools](itertools.md)** - `accumulate()` yields every intermediate result of the fold `reduce()` returns only the last of
- **[abc](abc.md)** - `ABCMeta.register()` and `get_cache_token()`, which decide when a dispatch cache is cleared
- **[weakref](weakref.md)** - `WeakKeyDictionary`, the structure a dispatch cache is, so a collected class costs it nothing
