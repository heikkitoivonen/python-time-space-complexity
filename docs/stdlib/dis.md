# dis Module Complexity

The `dis` module decodes CPython bytecode into readable instructions. Every entry point works on
one code object at a time; the ones that decode it read its line table, collect its jump targets,
then walk the bytecode front to back. `dis()` repeats that for the code objects nested inside what
it is given; everything else stays on the one code object.

`n` is the length of one code object's bytecode in code units - instructions plus their inline
cache entries, `len(code.co_code) // 2`. `j` is its jump instructions and `t` its distinct jump
targets, so `t ≤ j ≤ n`. `k` is the entries in its constant, name and variable tables, and `f` is
the frames in a traceback. Formatting one constant or name is treated as O(1). A source string is
compiled first, which adds the cost of compiling it.

## Complexity Reference

### Disassembly

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dis.dis(x=None, *, file=None, depth=None, ...)` | O(n + j·t) per code object | O(n) | Also disassembles every code object nested in `x`, down to `depth`; a class or module first sorts its m attributes, O(m log m); with no argument, the last traceback |
| `dis.disassemble(code, lasti=-1, *, file=None, ...)`, `dis.disco` | O(n + j·t) | O(n) | This code object only, not the ones nested in it |
| `dis.distb(tb=None, *, file=None, ...)` | O(n + j·t) | O(n) | Disassembles the frame of the entry it is given; with no argument, walks the last traceback to its innermost frame first, O(f) |
| `dis.code_info(x)` | O(k) | O(k) | Reads the code object's tables, not its bytecode, so `n` does not enter |
| `dis.show_code(x, *, file=None)` | O(k) | O(k) | Prints `code_info(x)` |
| `python -m dis [infile]` | O(n + j·t) per code object | O(n) | Compiles the file, then `dis()` on the module |

### Instruction Streams

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dis.get_instructions(x, *, first_line=None, ...)` | O(n + j·t) | O(n) | Lazy, one `Instruction` at a time, but the line table and jump targets are collected before the first one |
| `dis.findlinestarts(code)` | O(n) | O(1) | Generator of `(offset, lineno)` pairs |
| `dis.findlabels(code)` | O(n + j·t) | O(t) | Takes the raw bytes, `code.co_code`; returns the jump-target offsets as a list |
| `dis.stack_effect(opcode, oparg=None, *, jump=None)` | O(1) | O(1) | Table lookup for one opcode |

### Bytecode

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dis.Bytecode(x, *, first_line=None, current_offset=None, ...)` | O(n) | O(n) | Reads the line table at construction; decodes nothing yet |
| Iterating a `Bytecode` | O(n + j·t) | O(n) | Every `iter()` is a fresh `get_instructions()` pass |
| `Bytecode.dis()` | O(n + j·t) | O(n) | Returns the listing as one string; this code object only, unlike `dis.dis()` |
| `Bytecode.info()` | O(k) | O(k) | Same as `code_info()` |
| `Bytecode.from_traceback(tb)` | O(f + n) | O(n) | Walks to the innermost frame, where the exception was raised |
| `Bytecode.codeobj`, `Bytecode.first_line` | O(1) | O(1) | Stored at construction |

### Instruction and Positions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Instruction.opname`, `Instruction.opcode`, `Instruction.arg`, `Instruction.argval`, `Instruction.argrepr`, `Instruction.offset`, `Instruction.starts_line`, `Instruction.is_jump_target` | O(1) | O(1) | Set while decoding; reading one does no further work |
| `Instruction.positions` | O(1) | O(1) | Python 3.11+ |
| `Instruction.oparg`, `Instruction.baseopcode`, `Instruction.baseopname`, `Instruction.start_offset`, `Instruction.cache_offset`, `Instruction.end_offset`, `Instruction.line_number`, `Instruction.jump_target`, `Instruction.cache_info` | O(1) | O(1) | Python 3.13+ |
| `dis.Positions`, `Positions.lineno`, `Positions.end_lineno`, `Positions.col_offset`, `Positions.end_col_offset` | O(1) | O(1) | Python 3.11+; a field is `None` where the location is unknown |

### Opcode Collections

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dis.opname`, `dis.opmap`, `dis.cmp_op` | O(1) | O(1) | `opname[op]` indexes a list; `opmap[name]` is a dict lookup |
| `dis.hasconst`, `dis.hasname`, `dis.haslocal`, `dis.hasfree`, `dis.hascompare`, `dis.hasjrel`, `dis.hasjabs` | O(1) | O(1) | Lists: `op in dis.hasconst` scans one, so build a `set` to test many instructions |
| `dis.hasarg`, `dis.hasexc` | O(1) | O(1) | Python 3.12+; lists, like the others |
| `dis.hasjump` | O(1) | O(1) | Python 3.13+; `hasjrel` is the same list |
| `dis.HAVE_ARGUMENT`, `dis.EXTENDED_ARG` | O(1) | O(1) | Integer constants |

## Disassembling Code

### Listing a Function

`dis()` writes the listing to `file`, standard output by default. `Bytecode.dis()` produces the
same listing for a single code object and returns it as a string.

```python
import dis
import io

def add(x, y):
    return x + y

buffer = io.StringIO()
dis.dis(add, file=buffer)  # O(n + j·t)
listing = buffer.getvalue()

assert 'RETURN_VALUE' in listing
assert dis.Bytecode(add).dis() == listing  # O(n + j·t), returned as a string
```

### Nested Code Objects

`dis()` follows every code object stored among another's constants: inner functions, lambdas and
class bodies, each at its own O(n + j·t). `disassemble()` and `Bytecode.dis()` stop at the code
object they are given, and `depth` limits how far `dis()` goes.

```python
import dis
import io

def outer():
    def inner():
        return 1
    return inner

def render(**options):
    buffer = io.StringIO()
    dis.dis(outer, file=buffer, **options)
    return buffer.getvalue()

assert 'Disassembly of <code object inner' in render()  # outer, then inner
assert 'Disassembly of' not in render(depth=0)  # outer only

buffer = io.StringIO()
dis.disassemble(outer.__code__, file=buffer)  # O(n + j·t) - outer only
assert 'Disassembly of' not in buffer.getvalue()
assert 'Disassembly of' not in dis.Bytecode(outer).dis()
```

## Iterating Instructions

### One Instruction at a Time

`get_instructions()` yields `Instruction` named tuples lazily, but it collects the line table and
the jump targets before the first one, so even `next()` once costs O(n + j·t). A `Bytecode` is a
reusable version of the same iterator: each pass over it starts again from the beginning.

```python
import dis
from collections import Counter

def total(values):
    result = 0
    for value in values:
        result += value
    return result

instructions = dis.get_instructions(total)  # O(n + j·t) once the first is taken
first = next(instructions)
assert first.offset == 0

counts = Counter(instr.opname for instr in dis.Bytecode(total))  # O(n + j·t)
assert counts['RETURN_VALUE'] == 1

bytecode = dis.Bytecode(total)  # O(n) - decodes nothing yet
assert len(list(bytecode)) == len(list(bytecode))  # two full passes
```

### Branch-Heavy Code

Each jump target found is checked against the targets already found before it is kept, which is
the j·t term. Ordinary functions have few targets; generated code whose thousands of branches each
jump somewhere new makes every disassembly quadratic.

```python
import dis

source = "def classify(x):\n"
source += "".join(f"    if x == {i}: return {i}\n" for i in range(200))
source += "    return -1\n"
namespace = {}
exec(source, namespace)
code = namespace['classify'].__code__

labels = dis.findlabels(code.co_code)  # O(n + j·t)
assert len(labels) == len(set(labels)) == 200  # one target per `if`

targets = sum(instr.is_jump_target for instr in dis.get_instructions(code))
assert targets == 200
```

## Code Object Metadata

`code_info()` formats the code object's names, constants, variables and flags. It never decodes the
bytecode, so a long function costs no more than a short one with the same tables.

```python
import dis
import io

def scale(values, factor):
    return [value * factor for value in values]

info = dis.code_info(scale)  # O(k)
assert info.splitlines()[0].split() == ['Name:', 'scale']
assert 'Variable names:' in info
assert dis.Bytecode(scale).info() == info

buffer = io.StringIO()
dis.show_code(scale, file=buffer)  # O(k)
assert buffer.getvalue() == info + '\n'
```

## Tracebacks

`Bytecode.from_traceback()` walks to the innermost frame, where the exception was raised.
`distb()` given a traceback disassembles the frame of the entry it is given instead; only with no
argument does it walk to the innermost frame of the last traceback.

```python
import dis
import io

def inner():
    return 1 / 0

def outer():
    return inner()

try:
    outer()
except ZeroDivisionError as error:
    tb = error.__traceback__

bytecode = dis.Bytecode.from_traceback(tb)  # O(f + n)
assert bytecode.codeobj is inner.__code__

def render(disassembler, *args):
    buffer = io.StringIO()
    disassembler(*args, file=buffer)
    return buffer.getvalue()

# this entry's frame: the module, not inner()
assert render(dis.distb, tb) == render(dis.disassemble, tb.tb_frame.f_code, tb.tb_lasti)
assert tb.tb_frame.f_code is not inner.__code__
```

## Opcode Collections

The `has*` collections are lists, so testing membership scans one. Turn the list into a set once
when classifying many instructions.

```python
import dis

def greet():
    return 'hello'

const_ops = set(dis.hasconst)  # O(1) - bounded by the opcode count
loads = [instr.argval for instr in dis.get_instructions(greet) if instr.opcode in const_ops]
assert loads == ['hello']

assert dis.opname[dis.opmap['POP_TOP']] == 'POP_TOP'  # O(1)
assert dis.stack_effect(dis.opmap['POP_TOP']) == -1  # O(1)
assert isinstance(dis.hasconst, list)
```

## Common Patterns

### Finding the Globals a Function Reads

```python
import dis

def area(radius):
    return pi * radius ** 2 + abs(radius)

reads = {
    instr.argval
    for instr in dis.get_instructions(area)  # O(n + j·t)
    if instr.opname == 'LOAD_GLOBAL'
}
assert reads == {'pi', 'abs'}
```

## Performance Best Practices

✅ **Do**:

- Keep the instructions in a list when you need several passes; each pass over a `Bytecode`
  collects the jump targets again
- Build a `set` from a `has*` list before testing many instructions against it
- Use `code_info()` or `Bytecode.info()` for a code object's metadata: they do not decode the
  bytecode
- Pass `depth=0`, or call `disassemble()`, when the nested code objects are not wanted

❌ **Avoid**:

- `dis.dis()` on a module or class to look at one function - it disassembles every code object it
  reaches
- Disassembling generated functions with thousands of distinct branch targets; the j·t term makes
  each pass quadratic

## Version Notes

- **Python 3.11+**: Disassembly looks each instruction's offset up in a hash table of jump targets;
  on 3.10 it scans the list of them, so every row that decodes instructions is O(n + n·t)
  there; `findlabels()` itself is unchanged
- **Python 3.11+**: Added `Positions` and `Instruction.positions`
- **Python 3.12+**: Added `hasarg` and `hasexc`
- **Python 3.13+**: Added `hasjump` and the `Instruction` fields in the table above.
  `Instruction.starts_line` is a bool, with the line number in `line_number`; before 3.13 it held
  the line number or `None`
- **Python 3.13+**: `findlinestarts()` can yield `None` as a line number, for bytecode with no
  source line
- **All Python 3**: Bytecode is a CPython implementation detail; opcode names and counts change
  between releases

## Related Modules

- **[opcode](opcode.md)** - the opcode tables `dis` re-exports
- **[inspect](inspect.md)** - signatures and source without decoding bytecode
- **[ast](ast.md)** - the tree a source string becomes before it is compiled
- **[traceback](traceback.md)** - formatting the tracebacks `distb()` and `from_traceback()` read
