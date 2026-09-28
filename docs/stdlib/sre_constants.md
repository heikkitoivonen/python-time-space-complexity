# sre_constants Module Complexity

The `sre_constants` module holds the vocabulary shared by [sre_parse](sre_parse.md),
[sre_compile](sre_compile.md) and the C matcher: the opcodes a parse tree and a compiled code list
are made of, the flag bits, the engine's limits, and the exception class. On Python 3.10 it is the
module [re](re.md) itself imports. From Python 3.11 it is a deprecated alias: importing it issues
a `DeprecationWarning` and copies the names of the private `re._constants` module. The module has
never been documented, and opcode values change between releases, so nothing here is safe to store
or compare across Python versions.

Every name is a value computed at import, so reading one is O(1). The opcodes are `int`
subclasses that print as their name; the tables that map one opcode to another are dicts, and the
lists are indexed by opcode value.

## Complexity Reference

### Opcodes

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import sre_constants` | O(1) | O(1) | Python 3.11+: warns on the first import only; the names are the same objects as `re._constants`'s |
| `sre_constants.OPCODES`, `sre_constants.ATCODES`, `sre_constants.CHCODES` | O(1) | O(1) | Lists of the opcodes, anchor codes and category codes; indexing one by an opcode's value gives that opcode back |
| `sre_constants.LITERAL`, `sre_constants.IN`, `sre_constants.BRANCH`, `sre_constants.SUBPATTERN`, `sre_constants.MAX_REPEAT`, `sre_constants.MIN_REPEAT` and the other opcode names | O(1) | O(1) | `int` subclasses with a `.name`; the parser tests them with `is`. `MIN_REPEAT` and `MAX_REPEAT` appear only in parse trees and are left out of `OPCODES` |
| `sre_constants.AT_BEGINNING`, `sre_constants.CATEGORY_DIGIT` and the other anchor and category names | O(1) | O(1) | The members of `ATCODES` and `CHCODES` |
| `sre_constants.ATOMIC_GROUP`, `sre_constants.POSSESSIVE_REPEAT`, `sre_constants.POSSESSIVE_REPEAT_ONE` | O(1) | O(1) | Python 3.11+; Python 3.10 has a `CALL` opcode instead, which the parser never produces |

### Opcode maps

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_constants.OP_IGNORE`, `sre_constants.OP_LOCALE_IGNORE`, `sre_constants.OP_UNICODE_IGNORE` | O(1) | O(1) | Dicts from a case-sensitive opcode to the one used under `IGNORECASE` |
| `sre_constants.AT_MULTILINE`, `sre_constants.AT_LOCALE`, `sre_constants.AT_UNICODE` | O(1) | O(1) | Dicts from an anchor to its `MULTILINE`, `LOCALE` or `UNICODE` form |
| `sre_constants.CH_LOCALE`, `sre_constants.CH_UNICODE` | O(1) | O(1) | Dicts from a category to its `LOCALE` or `UNICODE` form |
| `sre_constants.CH_NEGATE` | O(1) | O(1) | Python 3.14+; a dict from each category to its complement |

### Flags and limits

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_constants.SRE_FLAG_IGNORECASE`, `SRE_FLAG_LOCALE`, `SRE_FLAG_MULTILINE`, `SRE_FLAG_DOTALL`, `SRE_FLAG_UNICODE`, `SRE_FLAG_VERBOSE`, `SRE_FLAG_DEBUG`, `SRE_FLAG_ASCII` | O(1) | O(1) | Plain ints equal to the matching `re` flags |
| `sre_constants.SRE_FLAG_TEMPLATE` | O(1) | O(1) | Python 3.10-3.12 only, like `re.TEMPLATE` |
| `sre_constants.SRE_INFO_PREFIX`, `SRE_INFO_LITERAL`, `SRE_INFO_CHARSET` | O(1) | O(1) | Bits in the header the compiler writes at the start of a code list |
| `sre_constants.MAGIC` | O(1) | O(1) | A version stamp the compiler and the C matcher must agree on; it changes between releases |
| `sre_constants.MAXREPEAT` | O(1) | O(1) | The repeat count that means "no upper bound", as in `a*`; the same value as `_sre.MAXREPEAT` |
| `sre_constants.MAXGROUPS` | O(1) | O(1) | The limit on a pattern's groups, counting group 0, so at most `MAXGROUPS - 1` can be opened; it differs between releases and builds |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `sre_constants.error`, `sre_constants.PatternError` | O(1) | O(1) | The class `re.error` names; `PatternError` is Python 3.13+, with `error` an alias |

## Reading a Parse Tree

A parse tree is a list of `(opcode, argument)` pairs, and the opcodes are the singletons defined
here. Test them with `is`, and use `.name` rather than the integer value, which moves between
releases.

```python
import re
import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', DeprecationWarning)
    import sre_constants
    import sre_parse

op, (low, high, body) = sre_parse.parse('a*')[0]
assert op is sre_constants.MAX_REPEAT and op.name == 'MAX_REPEAT'  # O(1)
assert (low, high) == (0, sre_constants.MAXREPEAT)  # no upper bound
assert body[0] == (sre_constants.LITERAL, ord('a'))

# The lists are indexed by opcode value
assert sre_constants.OPCODES[sre_constants.LITERAL] is sre_constants.LITERAL  # O(1)
assert sre_constants.OP_IGNORE[sre_constants.LITERAL] is sre_constants.LITERAL_IGNORE  # O(1)

# The flags are the numbers the re flags stand for
assert sre_constants.SRE_FLAG_IGNORECASE == re.IGNORECASE
assert sre_constants.error is re.error
```

## Performance Best Practices

✅ **Do**:

- Use the `re` flags and `re.error` in code that only matches text; they are the same values and
  the supported names
- Compare opcodes by identity or by `.name`

❌ **Avoid**:

- Storing opcode numbers, or `MAGIC`, across Python versions - both change between releases
- New code that imports the module on Python 3.11+ - it warns, and nothing in it is promised to
  stay

## Version Notes

- **Python 3.11+**: A deprecated alias for `re._constants`; importing it issues a
  `DeprecationWarning`, and `re` no longer imports it
- **Python 3.13+**: `PatternError` is the exception's name, with `error` kept as an alias, and
  `SRE_FLAG_TEMPLATE` is gone
- **All Python 3**: Undocumented; the deprecation names no removal release

## Related Modules

- **[re](re.md)** - the public flags and exception, and the cost of matching
- **[sre_parse](sre_parse.md)** - builds parse trees out of these opcodes
- **[sre_compile](sre_compile.md)** - turns them into the codes the matcher runs
