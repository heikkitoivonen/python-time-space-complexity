# ctypes Module Complexity

The `ctypes` module loads shared libraries, calls the C functions in them, and lays out C data -
numbers, strings, arrays, structures and pointers - in memory Python can read and write. Its own
work is marshalling: converting arguments on the way into a call and results on the way out, and
copying bytes between C memory and Python objects. Most of it is O(1) per value; most of what is
not is a copy, and the page marks where one happens.

`n` is the bytes of the C object an operation creates, copies or reads - a buffer, array,
structure, slice or NUL-terminated string - and an array's element count is proportional to it.
`f` is the fields in a `Structure` or `Union`'s `_fields_`, `a` is the arguments of one foreign
call or prototype, and `d` is the shared libraries loaded in the process. The work inside the C
function a call reaches, and the dynamic loader's work in `dlopen()` and symbol lookup, belong to
the library and the platform: every bound here is the part `ctypes` adds.

## Complexity Reference

### CDLL and library loaders

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ctypes.CDLL(name, mode=DEFAULT_MODE, handle=None, use_errno=False, use_last_error=False, winmode=None)` | O(1) | O(1) | Plus the loader's `dlopen()`; `CDLL(None)` opens the running program on Unix |
| `ctypes.PyDLL(name, ...)` | O(1) | O(1) | A `CDLL` whose functions keep the GIL and raise a pending Python exception after the call |
| `ctypes.pythonapi` | O(1) | O(1) | A `PyDLL` over the interpreter's C API, opened at import |
| `ctypes.LibraryLoader(dlltype)` | O(1) | O(1) | |
| `ctypes.cdll.<name>`, `ctypes.pydll.<name>` | O(1) | O(1) | The first access loads the library and caches it on the loader; later ones return the same object |
| `LibraryLoader.LoadLibrary(name)` | O(1) | O(1) | Loads a new library object on every call; nothing is cached |
| `CDLL._handle`, `CDLL._name` | O(1) | O(1) | The loader's handle and the name it was given |
| `ctypes.DEFAULT_MODE`, `ctypes.RTLD_GLOBAL`, `ctypes.RTLD_LOCAL` | O(1) | O(1) | `dlopen()` mode flags |
| `ctypes.util.find_library(name)` | O(t) | O(t) | t = output of the programs it runs (`ldconfig -p` on Linux, then the compiler and linker if that fails); every call runs them again |
| `ctypes.util.dllist()` | O(d) | O(d) | Python 3.14+, where the platform can enumerate loaded libraries |

### Foreign functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `lib.name` | O(1) | O(1) | The first access looks the symbol up and caches the function on the library; later ones are an attribute read |
| `lib['name']` | O(1) | O(1) | Looks the symbol up and builds a new function object on every access |
| Calling a foreign function | O(a + n) | O(a + n) | Converts each argument and the result, plus the C function's own cost. n = the bytes of any structure passed or returned by value, or of a `str` converted for a `c_wchar_p`; scalars and pointers are O(1) each. `CDLL` functions release the GIL while C runs |
| `_CFuncPtr.argtypes` | O(a) | O(a) | Setting it checks every type; each type's `from_param()` then runs on its argument at every call |
| `_CFuncPtr.restype` | O(1) | O(1) | Converts the C return value; `None` means `void` |
| `_CFuncPtr.errcheck` | O(1) | O(1) | Called once per call with the result, the function and the arguments; its own cost is added to every call |
| `ctypes.CFUNCTYPE(restype, *argtypes, use_errno=False, use_last_error=False)` | O(a) | O(a) | Cached by result type, argument types and flags: the same signature returns the same class |
| `ctypes.PYFUNCTYPE(restype, *argtypes)` | O(a) | O(a) | Builds a new class on every call |
| `prototype(callable)` | O(a) | O(a) | A C function pointer that calls back into Python; each call from C costs one Python call plus O(a) conversion |
| `ctypes.ArgumentError` | O(1) | O(1) | Raised when an argument cannot be converted |

### Simple types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ctypes.c_bool`, `ctypes.c_byte`, `ctypes.c_ubyte`, `ctypes.c_short`, `ctypes.c_ushort`, `ctypes.c_int`, `ctypes.c_uint`, `ctypes.c_long`, `ctypes.c_ulong`, `ctypes.c_longlong`, `ctypes.c_ulonglong`, `ctypes.c_size_t`, `ctypes.c_ssize_t`, `ctypes.c_float`, `ctypes.c_double`, `ctypes.c_longdouble`, `ctypes.c_char`, `ctypes.c_wchar`, `ctypes.c_void_p` | O(1) | O(1) | Construction, `.value` and assignment; `ctypes.c_voidp` is `c_void_p` |
| `ctypes.c_int8`, `ctypes.c_int16`, `ctypes.c_int32`, `ctypes.c_int64`, `ctypes.c_uint8`, `ctypes.c_uint16`, `ctypes.c_uint32`, `ctypes.c_uint64` | O(1) | O(1) | Aliases of the platform type of that width |
| `ctypes.c_time_t`, `ctypes.SIZEOF_TIME_T` | O(1) | O(1) | Python 3.12+ |
| `ctypes.c_float_complex`, `ctypes.c_double_complex`, `ctypes.c_longdouble_complex` | O(1) | O(1) | Python 3.14+, where libffi supports C complex types |
| `ctypes.c_char_p(value)` | O(1) | O(1) | Points at the `bytes` object's own buffer and keeps a reference; nothing is copied |
| `ctypes.c_wchar_p(value)` | O(n) | O(n) | Converts the `str` into a new `wchar_t` buffer, here and whenever a `str` is passed as a `c_wchar_p` argument |
| `c_char_p.value`, `c_wchar_p.value` | O(n) | O(n) | Reads up to the NUL and builds a new `bytes` or `str` |
| `ctypes.py_object(obj)` | O(1) | O(1) | Holds a reference; `.value` is the same object |
| `_SimpleCData.value`, `_SimpleCData._type_` | O(1) | O(1) | The value, and the `struct`-style type code |

### Arrays and buffers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ctypes.c_int * length`, `ctypes.ARRAY(type, length)` | O(1) | O(1) | The array type is cached per item type and length, whatever the length |
| `ctypes.Array`, `Array._length_`, `Array._type_` | O(1) | O(1) | Base class, element count and element type |
| `ArrayType()`, `ArrayType(*items)` | O(n) | O(n) | Zero-filled; initializers are stored one by one |
| `array[i]`, `array[i] = value` | O(1) | O(1) | A structure or array element is read as a view sharing the array's memory, and assigned by copying its n bytes |
| `array[i:j]` | O(n) | O(n) | n = the bytes read; a list, or `bytes` or `str` for a character array |
| Iterating an array | O(n) | O(1) | One element at a time |
| `array.value`, `array.raw` | O(n) | O(n) | Character arrays: `.value` stops at the first NUL, `.raw` copies the whole array |
| `ctypes.create_string_buffer(init, size=None)` | O(n) | O(n) | A zero-filled `c_char` array; `bytes` input is copied in, and the default size leaves room for a NUL |
| `ctypes.c_buffer(init, size=None)` | O(n) | O(n) | Same as `create_string_buffer` |
| `ctypes.create_unicode_buffer(init, size=None)` | O(n) | O(n) | The same for `c_wchar` |
| `ctypes.resize(obj, size)` | O(n) | O(n) | n = the new size; copies the old contents into the larger block. `len()` does not change, and it cannot shrink below the type's size |

### Structure and Union

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `class S(ctypes.Structure): _fields_ = [...]` | O(f) | O(f) | The layout is computed once, when `_fields_` is assigned; O(f²) time before 3.14 |
| `ctypes.Union` | O(f) | O(f) | The same, with every field at offset 0; O(f) on every version |
| `Structure._fields_`, `Structure._pack_`, `Structure._align_`, `Structure._layout_`, `Structure._anonymous_` | O(1) | O(1) | Read when `_fields_` is assigned. `_anonymous_` adds a descriptor for every field of each member it names, so those fields count toward f; the others change the layout, not the bound. `_align_` is 3.13+, `_layout_` 3.14+ |
| `S(*args, **kwargs)` | O(n) | O(n) | Zero-filled, then one field store per argument |
| `s.field`, `s.field = value` | O(1) | O(1) | An array or structure field is read as a view into `s` and assigned by copying its n bytes; a character array field is read as `bytes` or `str`, O(n) in the field |
| `ctypes.BigEndianStructure`, `ctypes.LittleEndianStructure`, `ctypes.BigEndianUnion`, `ctypes.LittleEndianUnion` | O(f) | O(f) | Defined as a `Structure` or `Union` is, so the two structures take O(f²) time before 3.14; fields are byte-swapped on each access, still O(1). The two unions are 3.11+ |
| `ctypes.CField` | O(1) | O(1) | The descriptor behind each field, `S.field`; public as `ctypes.CField` in 3.14+ |
| `CField.name`, `CField.type`, `CField.offset`, `CField.size`, `CField.byte_offset`, `CField.byte_size`, `CField.bit_offset`, `CField.bit_size`, `CField.is_bitfield`, `CField.is_anonymous` | O(1) | O(1) | Python 3.14+ except `offset` and `size` |

### Pointers and references

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ctypes.POINTER(type)` | O(1) | O(1) | Cached per pointee type |
| `ctypes.pointer(obj)` | O(1) | O(1) | A pointer instance that keeps `obj` alive |
| `_Pointer.contents`, `_Pointer._type_` | O(1) | O(1) | `contents` builds a new object sharing the pointee's memory on every access |
| `ptr[i]`, `ptr[i] = value` | O(1) | O(1) | Assigning a structure or array copies its n bytes |
| `ctypes.byref(obj, offset=0)` | O(1) | O(1) | Builds no pointer type or instance |
| `ctypes.cast(obj, type)` | O(1) | O(1) | Shares the address and keeps `obj` alive |
| `ctypes.addressof(obj)`, `ctypes.sizeof(obj_or_type)`, `ctypes.alignment(obj_or_type)` | O(1) | O(1) | |
| `ctypes.SetPointerType(pointer, cls)` | O(1) | O(1) | Completes an incomplete pointer type; deprecated in 3.13 |

### Sharing and copying memory

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `_CData.from_buffer(source, offset=0)` | O(1) | O(1) | Shares a writable buffer and keeps `source` alive |
| `_CData.from_buffer_copy(source, offset=0)` | O(n) | O(n) | Copies |
| `_CData.from_address(address)` | O(1) | O(1) | Shares; nothing keeps that memory alive |
| `_CData.in_dll(library, name)` | O(1) | O(1) | Plus a symbol lookup; shares the library's variable |
| `_CData.from_param(obj)` | O(1) | O(1) | The per-argument conversion `argtypes` runs; O(n) for a `str` passed as `c_wchar_p` |
| `_CData._b_base_`, `_CData._b_needsfree_`, `_CData._objects` | O(1) | O(1) | The owning object, whether this one owns its memory, and the objects kept alive |
| `ctypes.memmove(dst, src, count)`, `ctypes.memset(dst, c, count)` | O(n) | O(1) | n = count |
| `ctypes.string_at(ptr, size=-1)`, `ctypes.wstring_at(ptr, size=-1)` | O(n) | O(n) | Copies into `bytes` or `str`; `size=-1` reads up to the NUL |
| `ctypes.memoryview_at(ptr, size, readonly=False)` | O(1) | O(1) | Python 3.14+; a view of the memory, no copy |
| `ctypes.get_errno()`, `ctypes.set_errno(value)` | O(1) | O(1) | The thread's private copy of `errno`, swapped around calls into a `use_errno=True` library; `set_errno` returns the old value |

### Windows only

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ctypes.WinDLL`, `ctypes.OleDLL`, `ctypes.windll`, `ctypes.oledll` | O(1) | O(1) | As `CDLL` and `cdll`, with the stdcall convention; `OleDLL` raises `OSError` for a failing `HRESULT` |
| `ctypes.WINFUNCTYPE(restype, *argtypes, use_errno=False, use_last_error=False)` | O(a) | O(a) | Cached like `CFUNCTYPE` |
| `ctypes.HRESULT` | O(1) | O(1) | |
| `ctypes.GetLastError()`, `ctypes.get_last_error()`, `ctypes.set_last_error(value)` | O(1) | O(1) | `GetLastError()` reads the system value; the other two read and write the private copy swapped around calls into a `use_last_error=True` library, as `get_errno` does |
| `ctypes.FormatError(code=None)`, `ctypes.WinError(code=None, descr=None)` | O(1) | O(1) | Plus the system's message lookup |
| `ctypes.COMError`, `COMError.hresult`, `COMError.text`, `COMError.details` | O(1) | O(1) | Public in 3.14+ |
| `ctypes.CopyComPointer(src, dst)`, `ctypes.DllCanUnloadNow()`, `ctypes.DllGetClassObject(rclsid, riid, ppv)` | O(1) | O(1) | COM helpers; `CopyComPointer` is public in 3.14+ |
| `ctypes.util.find_msvcrt()` | O(1) | O(1) | |
| `ctypes.wintypes` | O(1) | O(1) | Windows type names as aliases of the types above |

## Loading Libraries

Attribute access caches what it finds: `cdll.<name>` keeps the library, and `lib.<name>` keeps
the function, so both are an attribute read after the first time. The spellings that build a new
object - `LoadLibrary()` and `lib['name']` - skip that cache on purpose, which matters when two
callers need different `argtypes` on the same symbol.

```python
import ctypes

libc = ctypes.CDLL(None)  # O(1) plus dlopen() - the running program, on Unix

assert libc.strlen is libc.strlen          # O(1) - found once, then cached
assert libc['strlen'] is not libc['strlen']  # O(1) - a new function object each time

libc.strlen.argtypes = [ctypes.c_char_p]
libc.strlen.restype = ctypes.c_size_t
assert libc.strlen(b"hello") == 5  # O(a) conversion, then strlen's own O(n)
```

### Finding a Library by Name

`ctypes.util.find_library()` answers by running programs - `ldconfig -p` on Linux, then the
compiler and linker if that finds nothing - and reads their output. It caches nothing, so call it
once and keep the path.

```python
import ctypes
import ctypes.util
import sys

if sys.platform.startswith('linux'):
    path = ctypes.util.find_library('c')  # O(t) - runs ldconfig every call
    assert path is not None and path.startswith('libc')
    libc = ctypes.CDLL(path)
    assert libc.abs(-3) == 3
```

## Calling Foreign Functions

A call converts each argument, runs the C function, and converts the result. With `argtypes` set,
the conversion is each type's `from_param()`, run on every call; setting `argtypes` costs the same
order as one call's argument conversion, so it is a correctness choice rather than a speed one.
An `errcheck` hook runs after every call.

```python
import ctypes

libc = ctypes.CDLL(None)

labs = libc.labs
labs.argtypes = [ctypes.c_long]  # O(a) - checked once
labs.restype = ctypes.c_long     # O(1)
assert labs(-42) == 42           # O(a) per call

seen = []

def check(result, func, args):
    seen.append(result)  # runs after every call
    return result

labs.errcheck = check
labs(-1)
labs(-2)
assert seen == [1, 2]

try:
    labs("not a number")
except ctypes.ArgumentError as error:
    assert 'argument 1' in str(error)
else:
    raise AssertionError('a str was converted to a C long')
```

### Callbacks

A prototype wrapping a Python function gives C a function pointer. Every time C calls it, that is
a Python call and an O(a) conversion, so a C routine that calls back k times costs k Python calls
on top of its own work. `CFUNCTYPE()` caches the prototype class, but not the callback: keep a
reference to the callback for as long as C may call it.

```python
import ctypes

libc = ctypes.CDLL(None)

CMP = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
)
assert CMP is ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
)  # O(a) - the same class

calls = 0

def compare(left, right):
    global calls
    calls += 1
    return left[0] - right[0]

callback = CMP(compare)  # keep this alive while qsort runs

values = (ctypes.c_int * 6)(5, 1, 4, 2, 6, 3)
libc.qsort.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, CMP]
libc.qsort.restype = None
libc.qsort(values, len(values), ctypes.sizeof(ctypes.c_int), callback)

assert list(values) == [1, 2, 3, 4, 5, 6]
assert calls >= len(values) - 1  # one Python call per comparison qsort makes
```

## Strings and Buffers

A `c_char_p` built from `bytes` points at that object's own memory, so building it copies nothing;
reading `.value` back walks to the NUL and builds new `bytes`. A `c_wchar_p` cannot share a
`str`'s storage and converts it into a new `wchar_t` buffer. When C needs memory to write into,
allocate it with `create_string_buffer()`: O(n), zero-filled, and yours to reuse.

```python
import ctypes

data = b"hello"
pointer = ctypes.c_char_p(data)  # O(1) - shares data's buffer
assert pointer.value == data     # O(n) - reads to the NUL, builds new bytes

buffer = ctypes.create_string_buffer(16)  # O(n) - zero-filled
assert buffer.raw == b"\x00" * 16

buffer.value = b"hi"                        # O(n) - copies in, with a NUL
assert buffer.value == b"hi"               # O(n) - stops at the first NUL
assert buffer.raw[:3] == b"hi\x00"         # O(n) - the whole array

copied = ctypes.create_string_buffer(b"abc")  # O(n) - len + 1 for the NUL
assert ctypes.sizeof(copied) == 4
```

### Growing a Buffer

`resize()` enlarges the memory behind an object but not its type: `len()` and indexing still see
the original length, so reach the new bytes through a pointer or `string_at()`.

```python
import ctypes

buffer = ctypes.create_string_buffer(4)
ctypes.resize(buffer, 64)  # O(n) - copies the old contents into the new block
assert ctypes.sizeof(buffer) == 64
assert len(buffer) == 4

try:
    ctypes.resize(buffer, 2)
except ValueError as error:
    assert 'minimum size' in str(error)
else:
    raise AssertionError('resize shrank below the type size')
```

## Arrays and Structures

Array and structure types are built once: `c_int * n` is cached per item type and length, and a
structure's layout is computed when `_fields_` is assigned, in O(f) (O(f²) before 3.14). Creating an instance
zero-fills its n bytes. Reading a field or element is O(1), and one that is itself an array or a
structure comes back as a view into the parent's memory, not a copy.

```python
import ctypes

IntArray = ctypes.c_int * 5
assert IntArray is ctypes.c_int * 5  # O(1) - cached

values = IntArray(10, 20)  # O(n) - zero-filled, then two stores
assert list(values) == [10, 20, 0, 0, 0]  # O(n)
assert values[1:3] == [20, 0]             # O(n) in the slice

class Point(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int), ('y', ctypes.c_int)]  # O(f) - layout once

class Polygon(ctypes.Structure):
    _fields_ = [('count', ctypes.c_int), ('points', Point * 3)]

shape = Polygon(3)          # O(n)
corner = shape.points[1]    # O(1) - a view, not a copy
corner.x = 7
assert shape.points[1].x == 7

assert Point.y.offset == ctypes.sizeof(ctypes.c_int)  # O(1)
assert ctypes.sizeof(Polygon) == ctypes.sizeof(ctypes.c_int) * 7
```

### Byte Order

The endian variants lay fields out in a fixed byte order, swapping on each access. That is O(1)
per field, the same bound as a native structure.

```python
import ctypes

class Header(ctypes.BigEndianStructure):
    _fields_ = [
        ('magic', ctypes.c_uint16),
        ('flags', ctypes.c_uint16),
        ('length', ctypes.c_uint32),
    ]

header = Header(0x0102, 0, 5)
assert bytes(header) == b"\x01\x02\x00\x00\x00\x00\x00\x05"  # O(n)
assert header.length == 5  # O(1) - swapped on read
```

## Pointers and References

`pointer()` builds a pointer instance and keeps its target alive. When a C function only needs an
address for the length of one call, `byref()` passes it without building a pointer object at all.
`cast()` reinterprets an address as another pointer type, sharing the memory.

```python
import ctypes

value = ctypes.c_int(42)

pointer = ctypes.pointer(value)  # O(1)
assert pointer.contents.value == 42
pointer.contents.value = 100     # O(1) - writes through
assert value.value == 100

reference = ctypes.byref(value)  # O(1) - no pointer instance
assert not isinstance(reference, ctypes._Pointer)

as_bytes = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ubyte))  # O(1) - same address
assert ctypes.addressof(as_bytes.contents) == ctypes.addressof(value)

assert ctypes.POINTER(ctypes.c_int) is ctypes.POINTER(ctypes.c_int)  # O(1) - cached
```

## Sharing Memory Instead of Copying

Several pairs differ only in whether they copy. `from_buffer()` lays a C type over a writable
Python buffer and shares it; `from_buffer_copy()` copies. `string_at()` copies C memory into
`bytes`; on 3.14+, `memoryview_at()` returns a view of it instead.

```python
import ctypes

raw = bytearray(8)

shared = (ctypes.c_uint8 * 8).from_buffer(raw)       # O(1) - shares raw
copied = (ctypes.c_uint8 * 8).from_buffer_copy(raw)  # O(n) - copies raw

raw[0] = 9
assert shared[0] == 9
assert copied[0] == 0

buffer = ctypes.create_string_buffer(b"abc")
assert ctypes.string_at(buffer) == b"abc"         # O(n) - copies up to the NUL
assert ctypes.string_at(buffer, 2) == b"ab"       # O(n) - exactly size bytes

ctypes.memset(buffer, ord('z'), 2)                # O(n) time, O(1) space
assert buffer.value == b"zzc"

if hasattr(ctypes, 'memoryview_at'):
    view = ctypes.memoryview_at(buffer, 3)  # O(1) - no copy
    view[0] = ord('Z')
    assert buffer.value == b"Zzc"
```

## Common Patterns

### Reusing One Buffer Across Calls

Allocating once and handing C the same buffer on every call leaves each call its own cost, with
no buffer to allocate per call.

```python
import ctypes

libc = ctypes.CDLL(None)
libc.snprintf.restype = ctypes.c_int

buffer = ctypes.create_string_buffer(32)  # O(n) once
results = []
for number in (1, 22, 333):
    written = libc.snprintf(buffer, ctypes.sizeof(buffer), b"%d", ctypes.c_int(number))
    results.append(buffer.value)  # O(n) - copy out what was written
    assert written == len(buffer.value)

assert results == [b"1", b"22", b"333"]
```

## Performance Best Practices

✅ **Do**:

- Use attribute access (`lib.name`, `cdll.name`), which caches, over `lib['name']` and
  `LoadLibrary()`, which do not
- Call `ctypes.util.find_library()` once and keep the path; each call runs external programs
- Pass `byref(obj)` when a call only needs an address, rather than building a `pointer()`
- Allocate a buffer once with `create_string_buffer()` and reuse it
- Use `from_buffer()` or `memoryview_at()` when sharing will do; the `_copy` and `string_at`
  forms are O(n)
- Keep a reference to every callback for as long as C may call it

❌ **Avoid**:

- Reading `.value` of a `c_char_p` or `c_wchar_p` in a loop - each read is O(n)
- Passing a `str` as `c_wchar_p` repeatedly when a `create_unicode_buffer()` would convert it
  once
- Callbacks from C code that calls them many times, where the Python call dominates
- `PYFUNCTYPE()` in a loop; unlike `CFUNCTYPE()`, it builds a new class every time

## Version Notes

- **Python 3.11+**: Added `BigEndianUnion` and `LittleEndianUnion`
- **Python 3.12+**: Added `c_time_t` and `SIZEOF_TIME_T`
- **Python 3.13+**: Added `Structure._align_`; `SetPointerType` is deprecated
- **Python 3.14+**: Defining a `Structure` is O(f) in its fields, where earlier versions take
  O(f²); added `memoryview_at()`, `ctypes.util.dllist()`, `Structure._layout_`, the public
  `CField` type with its byte and bit attributes, and the complex types where libffi supports
  them

## Related Modules

- **[struct](struct.md)** - Packs and unpacks C layouts into `bytes` without loading any library
- **[array](array.md)** - Typed arrays of numbers without C interop
- **[mmap](mmap.md)** - Shared memory that `from_buffer()` can lay a structure over
