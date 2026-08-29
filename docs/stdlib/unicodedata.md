# unicodedata Module

The `unicodedata` module provides access to the Unicode Character Database (UCD),
including character names, categories, normalization, and digit/decimal values.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `name(ch)` | O(1) | O(1) | Lookup by code point; raises ValueError if unnamed |
| `lookup(name)` | O(m) | O(1) | m = name length; the name itself must be read |
| `category(ch)` | O(1) | O(1) | General category |
| `bidirectional(ch)` | O(1) | O(1) | Bidi class |
| `combining(ch)` | O(1) | O(1) | Canonical combining class |
| `decimal(ch)` / `digit(ch)` / `numeric(ch)` | O(1) | O(1) | Numeric properties |
| `normalize(form, s)` | O(n + k²) | O(n) worst | n = string length; k = longest run of combining marks. Returns the original object, allocating nothing, if it is already in that form |
| `is_normalized(form, s)` | O(1) for ASCII, else O(n) quick check, O(n + k²) worst | O(1) or O(n) | ASCII answers from a flag on the string; an inconclusive quick check falls back to `normalize()`, inheriting its bound and its space |

## Character Properties

```python
import unicodedata

# Basic properties - every lookup below is O(1), a table read by code point
ch = "é"
print(unicodedata.name(ch))       # LATIN SMALL LETTER E WITH ACUTE
print(unicodedata.category(ch))   # Ll
print(unicodedata.combining(ch))  # 0
print(unicodedata.bidirectional(ch))  # L

# Numeric properties
print(unicodedata.decimal("٢"))   # 2
print(unicodedata.digit("②"))     # 2
print(unicodedata.numeric("Ⅷ"))   # 8.0
```

## Name Lookup

```python
import unicodedata

# Lookup by name - O(m) in the name length, which has to be read either way
ch = unicodedata.lookup("GREEK SMALL LETTER MU")  # "μ"

# Safe name lookup with default - O(1)
name = unicodedata.name("Ω", "UNKNOWN")  # "GREEK CAPITAL LETTER OMEGA"
missing = unicodedata.name("😀", None)    # Name exists; returns string
```

## Normalization

```python
import unicodedata

text = "cafe\u0301"  # "e" + combining acute

# Normalize to NFC/NFD/NFKC/NFKD - O(n + k²). The whole string is scanned,
# and canonical ordering sorts each run of combining marks, so a long run
# adds O(k²) for that run on top of the scan. O(n) space is the worst case,
# not the usual one: a string already in the requested form is returned as
# the same object, with nothing allocated
nfc = unicodedata.normalize("NFC", text)
nfd = unicodedata.normalize("NFD", text)

print(text == nfc)  # False
print(text == nfd)  # True

# Check normalization - O(1) for an ASCII string, which is already known to
# be normalized from a flag, and O(n) for anything else the quick check can
# settle. When it cannot, it falls back to normalize() and inherits that
# bound, O(n + k²), and its O(n) allocation. Still worth it to skip a
# normalize() that would be a no-op
print(unicodedata.is_normalized("NFC", text))  # False
print(unicodedata.is_normalized("NFD", text))  # True
```

## Related Documentation

- [codecs Module](codecs.md)
- [encodings Module](encodings.md)
