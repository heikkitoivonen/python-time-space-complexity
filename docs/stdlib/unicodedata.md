# unicodedata Module

The `unicodedata` module provides access to the Unicode Character Database (UCD),
including character names, categories, normalization, and digit/decimal values.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `name(ch)` | O(1) | O(1) | Lookup by code point; raises ValueError if unnamed |
| `lookup(name)` | O(1) | O(1) | Lookup by name |
| `category(ch)` | O(1) | O(1) | General category |
| `bidirectional(ch)` | O(1) | O(1) | Bidi class |
| `combining(ch)` | O(1) | O(1) | Canonical combining class |
| `decimal(ch)` / `digit(ch)` / `numeric(ch)` | O(1) | O(1) | Numeric properties |
| `normalize(form, s)` | O(n) | O(n) | n = string length |
| `is_normalized(form, s)` | O(n) | O(1) | Checks normalization |

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

# Lookup by name - O(1), the name index is hashed, not scanned
ch = unicodedata.lookup("GREEK SMALL LETTER MU")  # "μ"

# Safe name lookup with default - O(1)
name = unicodedata.name("Ω", "UNKNOWN")  # "GREEK CAPITAL LETTER OMEGA"
missing = unicodedata.name("😀", None)    # Name exists; returns string
```

## Normalization

```python
import unicodedata

text = "cafe\u0301"  # "e" + combining acute

# Normalize to NFC/NFD/NFKC/NFKD - O(n) in the string, and allocates a new
# string, unlike the per-character lookups above
nfc = unicodedata.normalize("NFC", text)
nfd = unicodedata.normalize("NFD", text)

print(text == nfc)  # False
print(text == nfd)  # True

# Check normalization - O(n) time but O(1) space; use it to skip a
# normalize() that would be a no-op
print(unicodedata.is_normalized("NFC", text))  # False
print(unicodedata.is_normalized("NFD", text))  # True
```

## Related Documentation

- [codecs Module](codecs.md)
- [encodings Module](encodings.md)
