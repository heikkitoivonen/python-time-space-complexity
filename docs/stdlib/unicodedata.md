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
| `normalize(form, s)` | O(n) typical, O(k²) worst | O(n) | n = string length; k = longest run of combining marks |
| `is_normalized(form, s)` | O(n) | O(1) or O(n) | Quick check is O(1) space; an inconclusive result falls back to `normalize()` |

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

# Normalize to NFC/NFD/NFKC/NFKD - O(n) for ordinary text, and allocates a
# new string, unlike the per-character lookups above. Canonical ordering
# sorts each run of combining marks, so a long run costs O(k²) in that run
nfc = unicodedata.normalize("NFC", text)
nfd = unicodedata.normalize("NFD", text)

print(text == nfc)  # False
print(text == nfd)  # True

# Check normalization - O(n) time. The quick check needs O(1) space, but an
# inconclusive answer falls back to normalize(), which allocates O(n). Still
# worth it to skip a normalize() that would be a no-op
print(unicodedata.is_normalized("NFC", text))  # False
print(unicodedata.is_normalized("NFD", text))  # True
```

## Related Documentation

- [codecs Module](codecs.md)
- [encodings Module](encodings.md)
