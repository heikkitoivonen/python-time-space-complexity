# Locale Module

The `locale` module provides access to the POSIX locale database for language, currency, and formatting settings.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getlocale()` | O(1) | O(1) | Get current locale |
| `setlocale(category, locale)` | Varies | Varies | Depends on platform/C library |
| `localeconv()` | O(1) | O(1) | Get locale info |
| `format_string(format, value)` | O(n) | O(n) | n = formatted output size |
| `strxfrm(string)` | O(n) | O(n) | Transform string |
| `strcoll(s1, s2)` | O(n) | O(1) | Compare locale-aware |

## Common Operations

### Getting Locale Information

```python
import locale

# O(1) - get current locale
current = locale.getlocale()
# Returns: ('en_US', 'UTF-8')

# O(1) - get locale category
lang_locale = locale.getlocale(locale.LC_TIME)
# Get time/date locale

# O(1) - get default locale
default = locale.getdefaultlocale()
```

### Setting Locale

```python
import locale

# O(1) - set locale for all categories
locale.setlocale(locale.LC_ALL, '')  # Use environment settings

# O(1) - set specific category
locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
locale.setlocale(locale.LC_NUMERIC, 'de_DE.UTF-8')

# O(1) - reset to C locale
locale.setlocale(locale.LC_ALL, 'C')
```

## Common Use Cases

### Number Formatting

```python
import locale

# Set German locale - O(1)
locale.setlocale(locale.LC_NUMERIC, 'de_DE.UTF-8')

# O(n) format number - n = formatted output size
value = 1234567.89
formatted = locale.format_string("%.2f", value)
# Returns: "1.234.567,89"

# Reset to US English - O(1)
locale.setlocale(locale.LC_NUMERIC, 'en_US.UTF-8')
formatted = locale.format_string("%.2f", value)
# Returns: "1,234,567.89"
```

### Currency Formatting

```python
import locale

# O(1) - get locale conventions
conv = locale.localeconv()

# O(1) - access currency symbols
currency_symbol = conv['currency_symbol']  # '$', '€', etc.
int_currency = conv['int_currency_symbol']  # 'USD', 'EUR'
decimal_point = conv['decimal_point']

# O(n) - format currency value
amount = 99.99
formatted = locale.format_string(
    "%s%.2f",
    (conv['currency_symbol'], amount)
)
```

### Locale-Aware String Comparison

```python
import locale

# O(1) - set locale
locale.setlocale(locale.LC_COLLATE, 'en_US.UTF-8')

# Strings to compare
str1 = "café"
str2 = "cafè"

# O(n) where n = string length
# Using C strcoll function
result = locale.strcoll(str1, str2)
# Negative if str1 < str2, 0 if equal, positive if str1 > str2

# O(n) - transform for sorting
transformed1 = locale.strxfrm(str1)
transformed2 = locale.strxfrm(str2)

# Now can use regular string comparison
sorted_strings = sorted([str1, str2], key=locale.strxfrm)
```

### Locale-Aware Date Formatting

```python
import locale
import time

# O(1) - set locale for dates/times
locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')

# O(1) - format time with locale
current_time = time.localtime()
french_date = time.strftime('%A, %d %B %Y', current_time)
# "jeudi, 15 janvier 2024"

# Switch to German - O(1)
locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
german_date = time.strftime('%A, %d. %B %Y', current_time)
# "Donnerstag, 15. Januar 2024"
```

## Performance Tips

### Cache Locale Conversions

```python
import locale

class LocaleCache:
    """Cache locale conversion - O(1) lookup"""
    
    def __init__(self):
        self._cache = {}
        self._current_locale = None
    
    def format_number(self, value, format_str):
        """O(1) cached or O(n) new formatting"""
        locale_key = locale.getlocale()
        cache_key = (locale_key, format_str, str(value))
        
        if cache_key not in self._cache:
            # O(n) to format
            self._cache[cache_key] = locale.format_string(
                format_str, value
            )
        
        return self._cache[cache_key]

# Usage
cache = LocaleCache()
formatted = cache.format_number(1234.56, "%.2f")  # O(n)
formatted = cache.format_number(1234.56, "%.2f")  # O(1)
```

### Set Locale Once per Category

```python
import locale

# Bad: Multiple setlocale calls - varies by platform
for i in range(100):
    locale.setlocale(locale.LC_NUMERIC, 'de_DE.UTF-8')
    value = locale.format_string("%.2f", i)

# Good: Set once (avoids repeated C library calls)
locale.setlocale(locale.LC_NUMERIC, 'de_DE.UTF-8')
for i in range(100):
    value = locale.format_string("%.2f", i)  # O(n)
```

### Batch Sort with Locale

```python
import locale

# Bad: Call strxfrm for each comparison - O(n*m*log(m))
strings = ['café', 'apple', 'über', 'banana']
sorted_list = sorted(strings, key=locale.strxfrm)

# Better: Still O(n*log(n)) but efficient
# Already optimal with key function

# For very large lists, transform once:
def efficient_sort(strings):
    """Transform once, sort by transformed - O(n*log(n))"""
    # O(n*k) to transform where k = avg string length
    transformed = [(locale.strxfrm(s), s) for s in strings]
    
    # O(n*log(n)) to sort
    transformed.sort()
    
    # O(n) to extract originals
    return [s for _, s in transformed]
```

## Version Notes

- **Python 3.x**: `locale` module is available
- **Platform-specific**: Behavior depends on the underlying C library and locale data

## Related Documentation

- Time Module - Date/time operations
- [Codecs Module](codecs.md) - Encoding/decoding
- Unicodedata Module - Unicode properties
