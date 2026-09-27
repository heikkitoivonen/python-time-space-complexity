# unicodedata Module Complexity

The `unicodedata` module reads the Unicode Character Database compiled into CPython: per-character
properties, character names, and the four normalization forms. A property or name is a table read
for one code point; normalization is the one operation that walks a whole text.

`n` is the characters in the string being normalized or checked, and `m` is the characters in a
name passed to `lookup()`. Every property function takes exactly one character, so it has no size
variable; a longer string raises `TypeError`. Character names have a fixed maximum length, so
`name()` has none either.

## Complexity Reference

### Character properties

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `unicodedata.category(chr)` | O(1) | O(1) | General category, such as `'Lu'` |
| `unicodedata.bidirectional(chr)` | O(1) | O(1) | Bidi class; `''` if none is assigned |
| `unicodedata.combining(chr)` | O(1) | O(1) | Canonical combining class; `0` for a starter |
| `unicodedata.east_asian_width(chr)` | O(1) | O(1) | `'W'`, `'F'`, `'Na'`, `'H'`, `'A'` or `'N'` |
| `unicodedata.mirrored(chr)` | O(1) | O(1) | `1` if the character is mirrored in bidi text, else `0` |
| `unicodedata.decomposition(chr)` | O(1) | O(1) | The mapping as hex code points, with a `<tag>` for a compatibility one; `''` if none |
| `unicodedata.decimal(chr[, default])`, `unicodedata.digit(chr[, default])`, `unicodedata.numeric(chr[, default])` | O(1) | O(1) | Raise `ValueError` for a character without the value unless `default` is given |

### Names

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `unicodedata.name(chr[, default])` | O(1) | O(1) | Raises `ValueError` for an unnamed character unless `default` is given |
| `unicodedata.lookup(name)` | O(m) | O(m) | Case-insensitive; also accepts aliases and named sequences, and raises `KeyError` for an unknown name. A non-ASCII `name` is encoded to UTF-8 first |

### Normalization

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `unicodedata.normalize(form, unistr)` | O(n) on a patched CPython, O(n²) before; O(1) for ASCII on 3.11+ | O(n), or O(1) when returned unchanged | See the warning below for the patched releases. The input itself comes back when a quick check can confirm it is already in `form`; a string that is in `form` but contains a character the check can only call "maybe" is rebuilt |
| `unicodedata.is_normalized(form, unistr)` | O(n); O(1) for ASCII on 3.11+ | O(1), or O(n) when the quick check is inconclusive | An inconclusive check falls back to `normalize()`, but that stays O(n) even before the patch: the quick check answers `False` at the first out-of-order combining mark, so the fallback only sees marks already in order |

### UCD

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `unicodedata.unidata_version` | O(1) | O(1) | The Unicode version of the module's tables; each Python minor release may move it |
| `unicodedata.ucd_3_2_0` | O(1) | O(1) | The same functions against Unicode 3.2.0, as IDNA requires. Its `normalize()` and `is_normalized()` have no quick check, so both build the normal form in O(n) space even for ASCII, and `is_normalized()` shares the pre-patch quadratic |
| `unicodedata.UCD` | O(1) | O(1) | The type of `ucd_3_2_0`; it cannot be instantiated |

## Character Properties

Each property is a read from a table indexed by code point, so the cost does not depend on which
character is asked about.

```python
import unicodedata

ch = "é"
assert unicodedata.category(ch) == "Ll"       # O(1)
assert unicodedata.bidirectional(ch) == "L"   # O(1)
assert unicodedata.combining(ch) == 0         # O(1)
assert unicodedata.combining("\u0301") == 230
assert unicodedata.east_asian_width("中") == "W"  # O(1)
assert unicodedata.mirrored("(") == 1         # O(1)
assert unicodedata.decomposition(ch) == "0065 0301"         # O(1)
assert unicodedata.decomposition("ﬁ") == "<compat> 0066 0069"

assert unicodedata.decimal("٢") == 2   # O(1)
assert unicodedata.digit("②") == 2     # O(1)
assert unicodedata.numeric("Ⅷ") == 8.0  # O(1)
assert unicodedata.decimal("a", None) is None

try:
    unicodedata.category("ab")
except TypeError as error:
    assert "unicode character" in str(error)
else:
    raise AssertionError("a two-character string was accepted")
```

## Name Lookup

`name()` and `lookup()` go in opposite directions. `lookup()` also knows the aliases and named
sequences that `name()` never returns, so a named sequence can come back as more than one
character.

```python
import unicodedata

assert unicodedata.lookup("greek small letter mu") == "μ"  # O(m)
assert unicodedata.name("Ω") == "GREEK CAPITAL LETTER OMEGA"  # O(1)

# An alias resolves, but name() gives the formal name
gha = unicodedata.lookup("LATIN CAPITAL LETTER GHA")  # O(m)
assert unicodedata.name(gha) == "LATIN CAPITAL LETTER OI"

# A named sequence is several code points
assert len(unicodedata.lookup("LATIN CAPITAL LETTER A WITH MACRON AND GRAVE")) == 2

# A private-use character has no name
assert unicodedata.name("\ue000", None) is None  # O(1)
try:
    unicodedata.lookup("GREEK SMALL LETTER M")
except KeyError as error:
    assert "undefined character name" in str(error)
else:
    raise AssertionError("an unknown name was found")
```

## Normalization

`normalize()` runs a quick check over the string first. When the check can confirm the string is
already in the requested form, the same object comes back and nothing is allocated. Otherwise the
string is decomposed, its combining marks are put in canonical order, and for NFC and NFKC
recomposed, all into a new string.

```python
import unicodedata

decomposed = "cafe\u0301"  # "e" + combining acute

nfc = unicodedata.normalize("NFC", decomposed)  # O(n) time and space
assert nfc == "café" and len(nfc) == 4
assert unicodedata.normalize("NFD", nfc) == decomposed  # O(n)
assert unicodedata.normalize("NFKC", "ﬁ") == "fi"

# Confirmed by the quick check: the same object, nothing allocated
assert unicodedata.normalize("NFC", nfc) is nfc
assert unicodedata.normalize("NFD", decomposed) is decomposed

# Already NFC, but U+0301 can combine with some letters, so it is rebuilt
maybe = "q\u0301"
assert unicodedata.is_normalized("NFC", maybe)
assert unicodedata.normalize("NFC", maybe) is not maybe
```

!!! warning "Install a security-patched Python"
    Before the CVE-2026-3276 fix, CPython insertion-sorted each run of combining marks, so
    `normalize()` took O(n + Σrᵢ²) time for runs of rᵢ marks, O(n²) for one adversarial run. The
    fix is in Python 3.10.21, 3.11.16, 3.12.14, 3.13.14, 3.14.6 and later releases; distributors
    may backport it while keeping an older version number.

### Checking Before Normalizing

`is_normalized()` answers from the quick check whenever it can, allocating nothing. Only an
inconclusive check falls back to building the normal form and comparing.

```python
import unicodedata

assert unicodedata.is_normalized("NFC", "plain ascii")  # O(1) on 3.11+
assert unicodedata.is_normalized("NFC", "café")         # O(n), quick check only
assert not unicodedata.is_normalized("NFC", "cafe\u0301")
assert unicodedata.is_normalized("NFD", "cafe\u0301")

# Out-of-order combining marks answer False at the first one
assert not unicodedata.is_normalized("NFD", "a\u0301\u0316")
```

## The Unicode 3.2.0 Database

`ucd_3_2_0` offers the same functions against the tables IDNA was defined on. Its normalization
skips the quick check, so it rebuilds even ASCII input.

```python
import unicodedata

old = unicodedata.ucd_3_2_0
assert old.unidata_version == "3.2.0"
assert isinstance(old, unicodedata.UCD)

text = "ascii"
assert unicodedata.normalize("NFC", text) is text  # O(1) on 3.11+
assert old.normalize("NFC", text) is not text      # O(n), always rebuilt
assert old.normalize("NFC", text) == text

# Characters added after Unicode 3.2 are unassigned there
assert old.category("\u20b9") == "Cn" and unicodedata.category("\u20b9") == "Sc"
```

## Common Patterns

### Comparing Identifiers

Normalize both sides once, then compare the results. NFKC folds compatibility characters such as
ligatures and styled letters, and case folding folds case. Folding case can leave text outside
NFKC, and NFKC can produce capitals, so the key normalizes on both sides of the fold.

```python
import unicodedata

def key(text):
    folded = unicodedata.normalize("NFKC", text).casefold()  # O(n)
    return unicodedata.normalize("NFKC", folded)             # O(n)

assert key("Straße") == key("STRASSE")
assert key("ﬁle") == key("file")
assert key("\U0001d400") == key("a")  # MATHEMATICAL BOLD CAPITAL A
assert unicodedata.is_normalized("NFKC", key("\u01f0"))  # folding alone leaves NFKC
assert key("cafe\u0301") == key("café")
```

## Performance Best Practices

✅ **Do**:

- Normalize text once, at the boundary where it enters the program, and compare normalized forms after that
- Run a patched Python before normalizing untrusted text; an unpatched one is quadratic in a run of combining marks
- Use `is_normalized()` to skip work: when its quick check settles the answer it allocates nothing

❌ **Avoid**:

- `normalize()` inside a comparison loop - each call is O(n) on anything but ASCII
- `ucd_3_2_0` for anything but the protocols that require Unicode 3.2.0; it rebuilds even ASCII input

## Version Notes

- **Python 3.11+**: `normalize()` and `is_normalized()` answer an ASCII string in O(1); on 3.10
  both scan it
- **Python 3.10.21, 3.11.16, 3.12.14, 3.13.14, 3.14.6+**: `normalize()` is O(n) on a run of
  combining marks; earlier releases are O(n²) on an adversarial run (CVE-2026-3276)

## Related Modules

- **[stringprep](stringprep.md)** - Unicode 3.2.0 tables for internationalized-name preparation, built on `ucd_3_2_0`
- **[codecs](codecs.md)** - encoding and decoding text
- **[encodings](encodings.md)** - the `idna` codec, which normalizes with `ucd_3_2_0`
