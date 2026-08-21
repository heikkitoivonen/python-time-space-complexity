# Builtins Complexity

Everything Python gives you without an import: the built-in types, the built-in
functions, the constants, and the exception hierarchy. Each entry below links to a
page with the full breakdown; the tables here give the headline complexity so you
can find what you need at a glance.

## Built-in Types

| Type | Use Case | Avg Access | Avg Insert | Avg Delete |
|------|----------|-----------|-----------|-----------|
| `list` | Ordered sequences | O(1) | O(n) | O(n) |
| `tuple` | Immutable sequence | O(1) | - | - |
| `range` | Numeric sequences | O(1) | - | - |
| `str` | Text | O(1) | - | - |
| `bytes` | Binary data | O(1) | - | - |
| `dict` | Key-value mapping | O(1) | O(1) | O(1) |
| `set` | Unique items | - | O(1) | O(1) |
| `frozenset` | Immutable unique items | - | - | - |

### Sequence Types

- **[List](list.md)** - Most flexible sequence type
- **[Tuple](tuple.md)** - Immutable sequences
- **[Range](range.md)** - Lazy numeric sequences
- **[String](str.md)** - Text and character sequences
- **[Bytes & Bytearray](bytes.md)** - Binary data and mutable bytes

### Mapping & Set Types

- **[Dictionary](dict.md)** - Hash-based key-value storage
- **[Set](set.md)** - Unordered unique items
- **[Frozenset](frozenset.md)** - Immutable unique items

### Numeric & Boolean Types

- **[Integer](int.md)** - Arbitrary-precision whole numbers
- **[Float](float.md)** - IEEE 754 double precision
- **[Boolean](bool.md)** - Two singletons, a subclass of `int`

## Built-in Functions

### Iteration

Functions in this group return an iterator. Creating it is cheap; the cost listed
under Notes is what you pay to consume it.

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`iter()`](iter.md) | O(1) | O(1) | Wraps an iterable in an iterator |
| [`next()`](next.md) | O(1)* | O(1) | * cost depends on the underlying iterator |
| [`aiter()`](aiter.md) | O(1) | O(1) | Async counterpart of `iter()` |
| [`anext()`](anext.md) | O(1) | O(1) | Awaiting costs what the async generator costs |
| [`enumerate()`](enumerate.md) | O(1) | O(1) | O(n) to consume; yields `(index, item)` tuples |
| [`zip()`](zip.md) | O(1) | O(1) | O(n) to consume; stops at the shortest iterable |
| [`map()`](map.md) | O(1) | O(1) | O(n*k) to consume, k = function time |
| [`filter()`](filter.md) | O(1) | O(1) | O(n*k) to consume, k = predicate time |
| [`reversed()`](reversed.md) | O(1) | O(1) | O(n) to consume; needs `__reversed__` or `__getitem__` |

### Aggregation & Ordering

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`len()`](len.md) | O(1) | O(1) | Built-in containers cache their length |
| [`sum()`](sum.md) | O(n) | O(1) | O(n²) if misused to concatenate strings |
| [`min()`](min.md) | O(n) | O(1) | Must compare every item |
| [`max()`](max.md) | O(n) | O(1) | Must compare every item |
| [`sorted()`](sorted.md) | O(n log n) | O(n) | Timsort (≤3.10), Powersort (3.11+) |
| [`all()`](all.md) | O(n) | O(1) | Short-circuits on the first falsy item |
| [`any()`](any.md) | O(n) | O(1) | Short-circuits on the first truthy item |

### Numbers & Bases

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`abs()`](abs.md) | O(1) | O(1) | O(k) for a custom `__abs__()` |
| [`divmod()`](divmod.md) | O(1) | O(1) | O(n²) for arbitrary-precision integers |
| [`pow()`](pow.md) | O(log y) | O(1) | Fast exponentiation; 3-argument form stays modular |
| [`round()`](round.md) | O(1) | O(1) | Banker's rounding on exact halves |
| [`bin()`](bin.md) | O(log n) | O(log n) | Cost is the length of the output |
| [`hex()`](hex.md) | O(log n) | O(log n) | Cost is the length of the output |
| [`oct()`](oct.md) | O(log n) | O(log n) | Cost is the length of the output |

### Text & Characters

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`chr()`](chr.md) | O(1) | O(1) | Code point to character |
| [`ord()`](ord.md) | O(1) | O(1) | Character to code point |
| [`format()`](format.md) | O(n) | O(n) | n = length of the result |
| [`repr()`](repr.md) | O(n) | O(n) | Recurses into containers |
| [`ascii()`](ascii.md) | O(n) | O(n) | Like `repr()`, escaping non-ASCII |
| [`hash()`](hash.md) | O(k) | O(1) | O(n) for strings, cached after the first call |

### Objects, Attributes & Types

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`type()`](type_func.md) | O(1) | O(1) | O(n) in the three-argument class-creating form |
| [`isinstance()`](isinstance.md) | O(d) | O(1) | d = MRO depth; effectively O(1) in practice |
| [`issubclass()`](issubclass.md) | O(d) | O(1) | d = MRO depth; effectively O(1) in practice |
| [`callable()`](callable.md) | O(1) | O(1) | Checks for `__call__` |
| [`id()`](id.md) | O(1) | O(1) | Backs the `is` operator |
| [`getattr()`](getattr.md) | O(d) | O(1) | Instance dict hit is O(1) average |
| [`setattr()`](setattr.md) | O(1) | O(1) | Hash table insertion |
| [`hasattr()`](hasattr.md) | O(d) | O(1) | Same lookup as `getattr()`, exception caught |
| [`delattr()`](delattr.md) | O(1) | O(1) | Hash table deletion |
| [`dir()`](dir.md) | O(n log n) | O(n) | Dominated by sorting the result |
| [`vars()`](vars.md) | O(1) | O(1) | Returns the `__dict__` reference, no copy |
| [`super()`](super.md) | O(d) | O(d) | Walks the MRO, which is cached |
| [`property()`](property.md) | O(1) | O(1) | Descriptor creation and access |
| [`classmethod()`](classmethod.md) | O(1) | O(1) | Descriptor creation; lookup is O(d) |
| [`staticmethod()`](staticmethod.md) | O(1) | O(1) | Descriptor creation; lookup is O(d) |

### Type Constructors

| Constructor | Time | Space | Notes |
|-------------|------|-------|-------|
| [`bool()`](bool_func.md) | O(1) | O(1) | Containers answer via `__len__()`, which is O(1) |
| [`int()`](int_func.md) | O(1) | O(1) | O(n²) parsing a very long numeric string |
| [`float()`](float_func.md) | O(1) | O(1) | O(n) from a string |
| [`complex()`](complex_func.md) | O(1) | O(1) | O(n) from a string |
| [`str()`](str_func.md) | O(1) | O(1) | O(n) for containers and custom `__str__()` |
| [`bytes()`](bytes_func.md) | O(n) | O(n) | n = length of the source |
| [`bytearray()`](bytearray_func.md) | O(n) | O(n) | n = length of the source |
| [`memoryview()`](memoryview_func.md) | O(1) | O(1) | A view over the buffer, never a copy |
| [`list()`](list_func.md) | O(n) | O(n) | n = length of the iterable |
| [`tuple()`](tuple_func.md) | O(n) | O(n) | O(1) when the argument is already a tuple |
| [`dict()`](dict_func.md) | O(n) | O(n) | O(n²) worst case with hash collisions |
| [`set()`](set_func.md) | O(n) | O(n) | O(n²) worst case with hash collisions |
| [`frozenset()`](frozenset_func.md) | O(n) | O(n) | O(1) when the argument is already a frozenset |
| [`slice()`](slice.md) | O(1) | O(1) | Only stores indices; applying it costs O(k) |
| [`object()`](object_func.md) | O(1) | O(1) | The base of every class |

### Code Execution

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`eval()`](eval.md) | O(n + m) | O(n + m) | n = source length, m = evaluation cost |
| [`exec()`](exec.md) | O(n + m) | O(n + m) | n = source length, m = execution cost |
| [`compile()`](compile.md) | O(n) | O(n) | Parsing plus bytecode generation |
| [`globals()`](globals.md) | O(1) | O(1) | Returns the existing module dict |
| [`locals()`](locals_func.md) | O(1) | O(1) | O(m) in optimized function scopes |

### Input, Output & Debugging

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| [`print()`](print.md) | O(n) | O(n) | n = total output length; I/O dominates |
| [`input()`](input.md) | O(k) | O(k) | k = length of the line read |
| [`open()`](open.md) | O(1)* | O(1) | * a system call; reads and writes cost what they move |
| [`help()`](help.md) | O(n) | O(n) | n = size of the introspected surface |
| [`breakpoint()`](breakpoint.md) | O(1) | O(1) | Hands control to the debugger |

## Constants

| Constant | Time | Space | Notes |
|----------|------|-------|-------|
| [`None`](none.md) | O(1) | O(1) | Singleton; compare with `is` |
| [`True`](true.md) | O(1) | O(1) | Singleton `bool` |
| [`False`](false.md) | O(1) | O(1) | Singleton `bool` |
| [`NotImplemented`](notimplemented.md) | O(1) | O(1) | Returned by operators that decline |
| [`Ellipsis`](ellipsis.md) | O(1) | O(1) | The `...` singleton |

## Exceptions & Interpreter

- **[Exceptions](exceptions.md)** - The built-in exception hierarchy and raise/catch costs
- **[Interpreter Info](interpreter_info.md)** - `copyright`, `credits`, `license`
- **[Exit/Quit](exit_quit.md)** - `exit` and `quit`

## Key Concepts

### Amortized Complexity

Some operations like `list.append()` have **amortized O(1)** complexity. This means:

- Most append operations are O(1)
- Occasionally, a resize happens requiring O(n)
- Over many operations, the average is O(1)

### Lazy vs Eager

Several built-in functions return an iterator rather than a result. Calling them is
O(1) no matter how large the input; the real work happens as you consume the
iterator, and it never happens at all for items you skip. Wrapping the call in
`list()` makes it eager again and restores the O(n) space cost.

### Implementation Details

CPython uses:

- **Lists**: Dynamic arrays with over-allocation
- **Dicts**: Hash tables with open addressing
- **Sets**: Hash tables (similar to dicts)

## Version Notes

Different Python versions have optimizations:

- **Python 3.7+**: Dict insertion order guaranteed (language spec)
- **Python 3.9+**: New dict implementation improvements
- **Python 3.10+**: Additional optimizations for common operations

See [Versions](../versions/index.md) for detailed changelog by release.

## See Also

- [Standard Library](../stdlib/index.md)
- [Implementations](../implementations/index.md)
