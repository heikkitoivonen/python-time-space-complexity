# stringprep Module Complexity

The `stringprep` module exposes the tables of RFC 3454, the "stringprep" framework that protocols
such as IDNA's nameprep build on. It prepares nothing itself: each function answers one question
about one character, either whether it belongs to a table or what the table maps it to. A
profile such as `encodings.idna.nameprep()` is the loop that applies them to a string.

Every function takes a single character, a `str` of length 1, and not a code point: an `int` or a
longer string raises `TypeError` in all but `in_table_c11()`, which simply returns `False`. So
there is no size variable in the table below. `n` is the characters in a string you prepare with
them.
Category and bidirectional lookups read Unicode 3.2 data, whatever Unicode version the
interpreter's `unicodedata` reports.

## Complexity Reference

### Table A: unassigned code points

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stringprep.in_table_a1(code)` | O(1) | O(1) | Unassigned in Unicode 3.2, so a character assigned later still counts |

### Table B: mappings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stringprep.in_table_b1(code)` | O(1) | O(1) | Characters commonly mapped to nothing |
| `stringprep.map_table_b3(code)` | O(1) | O(1) | Case folding for use without normalization |
| `stringprep.map_table_b2(code)` | O(1) | O(1) | Case folding for use with NFKC normalization |

### Table C: prohibited characters

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stringprep.in_table_c11(code)`, `stringprep.in_table_c12(code)`, `stringprep.in_table_c11_c12(code)` | O(1) | O(1) | ASCII space, non-ASCII spaces, and both |
| `stringprep.in_table_c21(code)`, `stringprep.in_table_c22(code)`, `stringprep.in_table_c21_c22(code)` | O(1) | O(1) | ASCII controls, non-ASCII controls, and both |
| `stringprep.in_table_c3(code)` | O(1) | O(1) | Private use |
| `stringprep.in_table_c4(code)` | O(1) | O(1) | Non-character code points |
| `stringprep.in_table_c5(code)` | O(1) | O(1) | Surrogate codes |
| `stringprep.in_table_c6(code)` | O(1) | O(1) | Inappropriate for plain text |
| `stringprep.in_table_c7(code)` | O(1) | O(1) | Inappropriate for canonical representation |
| `stringprep.in_table_c8(code)` | O(1) | O(1) | Change display properties or are deprecated |
| `stringprep.in_table_c9(code)` | O(1) | O(1) | Tagging characters |

### Table D: bidirectional categories

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `stringprep.in_table_d1(code)` | O(1) | O(1) | Bidirectional category R or AL |
| `stringprep.in_table_d2(code)` | O(1) | O(1) | Bidirectional category L |

## Checking Characters

Each predicate does a fixed amount of work on one character. Pass the character itself; its code point is the
wrong type.

```python
import stringprep

assert stringprep.in_table_b1('\u00ad')  # O(1) - soft hyphen maps to nothing
assert stringprep.in_table_c11(' ')  # O(1) - ASCII space
assert stringprep.in_table_c12('\u3000')  # O(1) - ideographic space
assert stringprep.in_table_c21('\x07')  # O(1) - ASCII control
assert stringprep.in_table_c3('\ue000')  # O(1) - private use
assert stringprep.in_table_d1('\u05d0')  # O(1) - Hebrew letter, category R
assert stringprep.in_table_d2('A')  # O(1) - category L

try:
    stringprep.in_table_b1(ord('A'))
except TypeError:
    pass
else:
    raise AssertionError('a code point was accepted')
```

## Mapping Characters

Both mappings return a string, because folding one character can produce several. `map_table_b2`
is the one a profile applies before NFKC normalization, as nameprep does; `map_table_b3` is the
folding for a profile that does not normalize.

```python
import stringprep

assert stringprep.map_table_b3('A') == 'a'        # O(1)
assert stringprep.map_table_b3('\u00df') == 'ss'  # O(1) - sharp s folds to two characters
assert stringprep.map_table_b2('\u2122') == 'tm'  # O(1) - trademark sign
```

## Preparing a String

A profile asks the tables a fixed set of questions about each character, so preparing a string
is O(n) time and O(n) space for the result. `encodings.idna.nameprep()` is that loop for domain
labels: it maps with B.1 and B.2, normalizes, and then checks the prohibited and bidirectional
tables.

```python
from encodings.idna import nameprep

assert nameprep('Stra\u00dfe\u00ad') == 'strasse'  # O(n) - fold, drop the soft hyphen
```

## Unicode 3.2 Tables

RFC 3454 is defined against Unicode 3.2, and the module's category lookups use that version's
data. A character assigned in a later Unicode version is unassigned as far as table A.1 is
concerned.

```python
import stringprep
import unicodedata

emoji = '\U0001F600'  # assigned after Unicode 3.2
assert unicodedata.category(emoji) == 'So'
assert stringprep.in_table_a1(emoji)  # O(1) - unassigned in Unicode 3.2
```

## Performance Best Practices

✅ **Do**:

- Use `encodings.idna.nameprep()`, or the `idna` codec, for domain labels: it is the O(n) loop
  over these tables
- Pass one-character strings, such as the items of iterating a `str`

❌ **Avoid**:

- Passing `ord(c)`: every function but `in_table_c11()` raises `TypeError`, and that one silently
  returns `False`
- Treating `in_table_a1()` as "unassigned today"; it answers for Unicode 3.2

## Version Notes

- **All Python 3**: Category and bidirectional lookups use Unicode 3.2 through
  `unicodedata.ucd_3_2_0`

## Related Modules

- **[encodings](encodings.md)** - `encodings.idna.nameprep()` applies these tables to a label
- **[codecs](codecs.md)** - the `idna` codec that calls nameprep
- **[unicodedata](unicodedata.md)** - the current Unicode database, and `ucd_3_2_0`
