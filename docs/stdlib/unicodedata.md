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
| `normalize(form, s)` | O(n) on a patched CPython, O(n²) before | O(n) worst | n = string length. The linear bound needs the CVE-2026-3276 fix, which counting-sorts long combining-mark runs — see the warning below. Returns the original object, allocating nothing, if it is already in that form |
| `is_normalized(form, s)` | O(1) for ASCII on 3.11+, else O(n) | O(1) or O(n) | On 3.11+ an ASCII string answers from a flag on the string object; 3.10 scans it like any other. An inconclusive quick check falls back to `normalize()` and allocates, but stays O(n) on any CPython: the check bails at the first combining-class inversion, and an inversion is exactly what would make `normalize()` superlinear |

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

# Normalize to NFC/NFD/NFKC/NFKD - O(n). The whole string is scanned, and
# security-patched CPython uses counting sort to order long combining-mark
# runs. O(n) space is the worst case, not the usual one: a string already in
# the requested form is returned as the same object, with nothing allocated
nfc = unicodedata.normalize("NFC", text)
nfd = unicodedata.normalize("NFD", text)

print(text == nfc)  # False
print(text == nfd)  # True

# Check normalization - O(1) on 3.11+ for an ASCII string, which is already
# known to be normalized from a flag on the string object (3.10 has no such
# short-circuit and scans it), and O(n) for anything else the quick check can
# settle. When it cannot, it falls back to normalize() and allocates - but it
# does not inherit the pre-fix quadratic, on any CPython. The check bails at
# the first combining-class inversion, and an inversion is precisely what
# makes the sort quadratic, so the fallback only ever runs on a run that is
# already ordered. Still worth it to skip a normalize() that would be a no-op
print(unicodedata.is_normalized("NFC", text))  # False
print(unicodedata.is_normalized("NFD", text))  # True
```

!!! warning "Install a security-patched Python"
    Before the CVE-2026-3276 fix, CPython insertion-sorted each combining-mark
    run. Its worst-case time was O(n + Σrᵢ²), reaching O(n²) for one adversarial
    run. The fix is included upstream in Python 3.10.21, 3.11.16, 3.12.14,
    3.13.14, 3.14.6, and later releases; distributors may backport it while
    retaining an older Python version number.

## Version Notes

- **Python 3.11+**: `is_normalized()` answers an ASCII string from a flag on the
  string object instead of scanning it. On 3.10 an ASCII string costs the same as
  any other of the same length
- **Python 3.10.21, 3.11.16, 3.12.14, 3.13.14, 3.14.6+**: `normalize()` orders long
  combining-mark runs with a counting sort (CVE-2026-3276). Earlier releases
  insertion-sort them, which is quadratic on an adversarial run

## Related Documentation

- [codecs Module](codecs.md)
- [encodings Module](encodings.md)
