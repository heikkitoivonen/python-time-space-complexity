# opcode Module Complexity

The `opcode` module holds the tables that describe CPython's bytecode instructions: the name of
each opcode number, the number of each name, and lists of the opcodes that share a property. `dis`
is built on it and re-exports every table. All of them are built once, when the module is
imported; reading one returns the same object every time and computes nothing.

`h` is the opcodes in one `has*` list. Every table is bounded by the interpreter's opcode count,
which is fixed for a given release, so building a `set` from a `has*` list is a one-off O(h).

## Complexity Reference

### Opcode tables

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `opcode.opmap`, `opmap[name]` | O(1) | O(1) | Dict from instruction name to opcode number |
| `opcode.opname`, `opname[op]` | O(1) | O(1) | List indexed by opcode number; an unused number reads `'<n>'` |
| `opcode.cmp_op` | O(1) | O(1) | Tuple of the six comparison operator strings |
| `opcode.HAVE_ARGUMENT` | O(1) | O(1) | Opcodes below it ignore their argument; use `hasarg` to test whether one uses it on 3.12+ |
| `opcode.EXTENDED_ARG` | O(1) | O(1) | The prefix opcode that widens the next instruction's argument |

### Opcode collections

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `opcode.hasconst`, `opcode.hasname`, `opcode.haslocal`, `opcode.hasfree`, `opcode.hascompare`, `opcode.hasjrel`, `opcode.hasjabs` | O(1) | O(1) | Lists; `hasjabs` is empty on 3.11+ |
| `opcode.hasarg`, `opcode.hasexc` | O(1) | O(1) | Python 3.12+; lists, like the others |
| `opcode.hasjump` | O(1) | O(1) | Python 3.13+; `hasjrel` is the same list |
| `op in opcode.hasconst`, on any `has*` list | O(h) | O(1) | A list scan; build a `set` once to test many instructions |

### Stack effects

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `opcode.stack_effect(opcode, oparg=None, *, jump=None)` | O(1) | O(1) | Independent of the size of `oparg`; `jump=None` gives the larger of the jump and no-jump effects |

## Looking Up Opcodes

Opcode numbers are a CPython implementation detail and change between releases, so look an
instruction up by name and keep the number only within one process.

```python
import opcode

load_const = opcode.opmap['LOAD_CONST']  # O(1) - dict lookup
assert opcode.opname[load_const] == 'LOAD_CONST'  # O(1) - list index

# Every name in opmap indexes back to itself through opname
assert all(opcode.opname[op] == name for name, op in opcode.opmap.items())

# A number no instruction uses reads as a placeholder
unused = next(op for op, name in enumerate(opcode.opname) if name.startswith('<'))
assert opcode.opname[unused] == f'<{unused}>'

assert opcode.cmp_op == ('<', '<=', '==', '!=', '>', '>=')
assert opcode.opname[opcode.EXTENDED_ARG] == 'EXTENDED_ARG'
```

## Testing Opcode Properties

The `has*` collections are lists, so `op in opcode.hasname` compares against each entry in turn.
Convert one to a set before classifying many instructions.

Whether an instruction uses its argument is `op in hasarg` on 3.12+. Comparing with
`HAVE_ARGUMENT` only holds in one direction there: opcodes below it still ignore their argument,
but some at or above it do too.

```python
import dis
import opcode

def scale(value, factor):
    return value * factor

names = set(opcode.hasname)    # O(h), once
locals_ = set(opcode.haslocal)  # O(h), once

instructions = list(dis.get_instructions(scale))
assert not any(instr.opcode in names for instr in instructions)  # O(1) per test
assert any(instr.opcode in locals_ for instr in instructions)

if hasattr(opcode, 'hasarg'):  # Python 3.12+
    takes_arg = set(opcode.hasarg)
    assert not any(op < opcode.HAVE_ARGUMENT for op in takes_arg)
else:
    takes_arg = {op for op in opcode.opmap.values() if op >= opcode.HAVE_ARGUMENT}

assert opcode.opmap['STORE_NAME'] in takes_arg
assert opcode.opmap['POP_TOP'] not in takes_arg
```

## Stack Effects

`stack_effect()` answers from a table or a formula for the one opcode it is given. An argument
that counts stack items, such as `BUILD_TUPLE`'s, enters the formula as a number, so a huge
`oparg` costs the same as a small one.

```python
import opcode

build_tuple = opcode.opmap['BUILD_TUPLE']
assert opcode.stack_effect(build_tuple, 3) == -2  # O(1) - pops three, pushes one
assert opcode.stack_effect(build_tuple, 2**30) == 1 - 2**30  # O(1), not O(oparg)

assert opcode.stack_effect(opcode.opmap['POP_TOP']) == -1  # O(1)
```

## Common Patterns

### Counting Instructions by Kind

```python
import collections
import dis
import opcode

def mean(items):
    total = 0
    for item in items:
        total += item
    return total / len(items)

kinds = {'local': set(opcode.haslocal), 'name': set(opcode.hasname)}  # O(h) per list

counts = collections.Counter()
for instr in dis.get_instructions(mean):
    for kind, ops in kinds.items():
        if instr.opcode in ops:  # O(1)
            counts[kind] += 1

assert counts['local'] >= 4
assert counts['name'] == 1  # the global `len`
```

## Performance Best Practices

✅ **Do**:

- Look opcodes up by name with `opmap`; the numbers change between releases
- Build a `set` from a `has*` list before testing many instructions against it
- Test `op in hasarg` on 3.12+ to find the instructions that use their argument

❌ **Avoid**:

- `op in opcode.hasconst` in a loop over every instruction - each test scans the list
- Hard-coding opcode numbers, or bytecode compiled by another release
- `op >= HAVE_ARGUMENT` on 3.12+ as the test for an argument: some opcodes at or above it ignore
  theirs

## Version Notes

- **Python 3.11+**: `hasjabs` is empty
- **Python 3.12+**: Added `hasarg` and `hasexc`. The tables also cover pseudo-instructions and
  instrumented opcodes, so `opname` is longer than 256 entries and `HAVE_ARGUMENT` no longer tells
  whether an opcode uses its argument
- **Python 3.13+**: Added `hasjump`; `hasjrel` is the same list.
  `stack_effect()` treats a missing `oparg` as 0 and ignores one the opcode does not use; before
  3.13 omitting it for an opcode that uses one, or passing one to an opcode that does not, raises
  `ValueError`
- **All Python 3**: Bytecode is a CPython implementation detail; opcode numbers, names and the
  contents of the `has*` lists change between releases

## Related Modules

- **[dis](dis.md)** - decodes bytecode into instructions, using these tables
- **[inspect](inspect.md)** - code objects and signatures without reading bytecode
