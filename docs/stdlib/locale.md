# locale Module Complexity

The `locale` module exposes the C library's locale: which conventions the process uses for
numbers, money, dates, messages and collation. The setting is process-wide, so changing it
changes every thread's formatting. `setlocale()` and collation go straight to the C library; the
number formatting functions are Python built on the conventions `localeconv()` reports.

`s` is the characters of a string argument, `a` and `b` are the characters of the two strings
`strcoll()` compares, `f` is the characters of a format string, `r` is the characters of the
result, and `n` is strings sorted. Locale names, category constants, the `localeconv()` table and
the `nl_langinfo()` key table are small and fixed, so looking one up is O(1). With
`grouping=True`, grouping a number re-slices its digits once per group, which adds O(d²) for a
number with `d` digits in its integer part. Loading a locale's data when `setlocale()` first
selects it is the C library's work and is not priced here.

## Complexity Reference

### Locale settings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locale.setlocale(category)` | O(1) | O(1) | Query only: returns the category's current name and changes nothing |
| `locale.setlocale(category, locale)` | Varies | Varies | The C library selects the locale; raises `locale.Error` if it is not installed. A `(language, encoding)` tuple goes through `normalize()` first |
| `locale.getlocale(category=LC_CTYPE)` | O(1) | O(1) | One `setlocale()` query, parsed through the alias table; `(None, None)` for the C locale. `LC_ALL` raises `TypeError` when the categories differ |
| `locale.getdefaultlocale(envvars=('LC_ALL', 'LC_CTYPE', 'LANG', 'LANGUAGE'))` | O(1) | O(1) | Works out the default locale without changing the current one; warns `DeprecationWarning` on Python 3.11 to 3.14.6 |
| `locale.getencoding()` | O(1) | O(1) | The current locale encoding, ignoring UTF-8 mode; Python 3.11+ |
| `locale.getpreferredencoding(do_setlocale=True)` | Varies | Varies | Answers UTF-8 at once in UTF-8 mode; otherwise, with `do_setlocale=True`, sets `LC_CTYPE` from the environment and back, which is not thread-safe. `do_setlocale=False` is O(1) |
| `locale.normalize(localename)` | O(1) | O(1) | At most four lookups in `locale_alias`; a name it does not know is returned unchanged |
| `locale.locale_alias`, `locale.locale_encoding_alias`, `locale.windows_locale` | O(1) | O(1) | The dictionaries `normalize()` and `getdefaultlocale()` consult; a lookup is a dict lookup |
| `locale.LC_CTYPE`, `locale.LC_COLLATE`, `locale.LC_TIME`, `locale.LC_MONETARY`, `locale.LC_NUMERIC`, `locale.LC_MESSAGES`, `locale.LC_ALL` | O(1) | O(1) | Integer categories |
| `locale.Error` | O(1) | O(1) | Raised by `setlocale()` for a locale that is not available |

### Conventions and language information

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locale.localeconv()` | O(1) | O(1) | A new dictionary of the numeric and monetary conventions on every call |
| `locale.CHAR_MAX` | O(1) | O(1) | The value a `localeconv()` field holds when the locale leaves it unspecified |
| `locale.nl_langinfo(option)` | O(1) | O(1) | Unix only; raises `ValueError` for a key it does not know |
| `locale.CODESET`, `locale.D_T_FMT`, `locale.D_FMT`, `locale.T_FMT`, `locale.T_FMT_AMPM`, `locale.AM_STR`, `locale.PM_STR`, `locale.RADIXCHAR`, `locale.THOUSEP`, `locale.YESEXPR`, `locale.NOEXPR`, `locale.CRNCYSTR`, `locale.ERA`, `locale.ERA_D_T_FMT`, `locale.ERA_D_FMT`, `locale.ERA_T_FMT`, `locale.ALT_DIGITS` | O(1) | O(1) | `nl_langinfo()` keys; `ERA` and `ALT_DIGITS` are empty in locales without them |
| `locale.DAY_1` ... `locale.DAY_7`, `locale.ABDAY_1` ... `locale.ABDAY_7`, `locale.MON_1` ... `locale.MON_12`, `locale.ABMON_1` ... `locale.ABMON_12` | O(1) | O(1) | `nl_langinfo()` keys for day and month names, `DAY_1` being Sunday |

### Collation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locale.strcoll(string1, string2)` | O(a + b) | O(a + b) | Both strings are converted in full before comparing, so strings that differ in their first character still cost their whole length |
| `locale.strxfrm(string)` | O(s) | O(s) | A key that compares with `<` as the string does with `strcoll()` |

### Number formatting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locale.format_string(f, val, grouping=False, monetary=False)` | O(f + r) | O(f + r) | `%` formatting with `LC_NUMERIC`'s decimal point, or `LC_MONETARY`'s with `monetary=True`; plus O(d²) per number with `grouping=True` |
| `locale.currency(val, symbol=True, grouping=False, international=False)` | O(r) | O(r) | Needs a locale that defines currency conventions; the C locale leaves `frac_digits` at `CHAR_MAX`. Plus O(d²) with `grouping=True` |
| `locale.str(float)` | O(1) | O(1) | `'%.12g'` with the locale's decimal point |
| `locale.localize(string, grouping=False, monetary=False)` | O(s) | O(s) | Puts the locale's decimal point into a `'.'`-formatted number; plus O(d²) with `grouping=True` |
| `locale.delocalize(string)` | O(s) | O(s) | Removes the thousands separator and turns the decimal point back into `'.'` |
| `locale.atof(string, func=float)` | O(s) | O(s) | `delocalize()`, then `func`; the bound is for the default `float` |
| `locale.atoi(string)` | O(s) | O(s) | `delocalize()`, then `int()` |

### C library message catalogues

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locale.gettext(msg)`, `locale.dgettext(domain, msg)`, `locale.dcgettext(domain, msg, category)` | O(s) | O(s) | The C library's `gettext()`; without a catalogue for the domain, `msg` comes back unchanged |
| `locale.textdomain(domain)` | O(1) | O(1) | Sets the C library's default domain; `None` only queries it |
| `locale.bindtextdomain(domain, dir)` | O(1) | O(1) | Where the C library looks for `domain`'s catalogues; `None` only queries it |
| `locale.bind_textdomain_codeset(domain, codeset)` | O(1) | O(1) | The encoding the C library converts `domain`'s messages to; `None` only queries it |

## Reading and Changing the Locale

A query costs a C call and changes nothing. Setting a category changes it for the whole process,
and a name the C library does not have raises `locale.Error` with the setting left as it was.

```python
import locale

previous = locale.setlocale(locale.LC_NUMERIC)  # O(1) - a query changes nothing
assert locale.setlocale(locale.LC_NUMERIC) == previous

assert locale.setlocale(locale.LC_NUMERIC, 'C') == 'C'  # every thread sees this
assert locale.getlocale(locale.LC_NUMERIC) == (None, None)  # O(1)
assert locale.localeconv()['decimal_point'] == '.'  # O(1)

try:
    locale.setlocale(locale.LC_NUMERIC, 'no_SUCH.locale')
except locale.Error as error:
    assert 'unsupported locale setting' in str(error)
else:
    raise AssertionError('a missing locale was accepted')
assert locale.setlocale(locale.LC_NUMERIC) == 'C'  # unchanged by the failure

locale.setlocale(locale.LC_NUMERIC, previous)
```

### Normalizing Locale Names

`normalize()` is a few dictionary lookups in `locale_alias`, whatever the table's size. It turns
the spellings people type into names `setlocale()` accepts, and leaves a name it does not know
alone rather than guessing.

```python
import locale

assert locale.normalize('en_US.utf8') == 'en_US.UTF-8'  # O(1)
assert locale.normalize('not-a-locale') == 'not-a-locale'
assert locale.locale_alias['en_us'] == 'en_US.ISO8859-1'  # O(1) dict lookup
```

## Formatting and Parsing Numbers

`format_string()` is `%` formatting followed by a rewrite of each numeric conversion into the
locale's conventions, so it costs the format string plus its result. `atof()`, `atoi()` and
`delocalize()` undo the rewrite in one pass over the string, so a number formatted in a locale
parses back in the same locale.

```python
import locale

locale.setlocale(locale.LC_NUMERIC, 'C')

text = locale.format_string('%.2f of %d', (1234.5, 7), grouping=True)  # O(f + r)
assert text == '1234.50 of 7'  # the C locale has '.' and no grouping

formatted = locale.format_string('%.2f', 1234.5)
assert locale.atof(formatted) == 1234.5  # O(s)
assert locale.atoi('1234') == 1234  # O(s)
assert locale.delocalize(formatted) == '1234.50'  # O(s)
assert locale.localize('1234.50') == formatted  # O(s)
assert locale.str(0.1 + 0.2) == '0.3'  # O(1) - '%.12g'
```

## Sorting Strings by Locale

`strcoll()` converts both of its strings in full on every call, even when they differ in the first
character. As a comparison function it pays that on each of the O(n log n) comparisons a sort
makes. `strxfrm()` pays the conversion once per string and returns a key that ordinary `<`
compares, so `key=locale.strxfrm` is the way to sort.

```python
import functools
import locale

locale.setlocale(locale.LC_COLLATE, 'C')
words = ['banana', 'apple', 'Cherry', 'apple pie']

by_key = sorted(words, key=locale.strxfrm)  # n strxfrm() calls
by_cmp = sorted(words, key=functools.cmp_to_key(locale.strcoll))  # a strcoll() per comparison

assert by_key == by_cmp == ['Cherry', 'apple', 'apple pie', 'banana']  # C: code point order
assert locale.strcoll('apple', 'banana') < 0  # O(a + b)
assert locale.strxfrm('apple') == 'apple'  # O(s) - C locale: an ASCII string is its own key
```

## Language Information

`nl_langinfo()` answers one fixed key at a time from the C library's tables for the category the
key belongs to: day and month names follow `LC_TIME`, the radix character follows `LC_NUMERIC`.
It is Unix only.

```python
import locale

locale.setlocale(locale.LC_TIME, 'C')
locale.setlocale(locale.LC_NUMERIC, 'C')

assert locale.nl_langinfo(locale.DAY_1) == 'Sunday'  # O(1)
assert locale.nl_langinfo(locale.ABMON_1) == 'Jan'
assert locale.nl_langinfo(locale.RADIXCHAR) == '.'

try:
    locale.nl_langinfo(-1)
except ValueError as error:
    assert 'unsupported langinfo constant' in str(error)
else:
    raise AssertionError('an unknown key was answered')
```

## C Library Message Catalogues

`gettext()`, `dgettext()` and `dcgettext()` translate through the C library's catalogues, the
ones C extensions use. Python code usually wants the [gettext](gettext.md) module instead, which
reads catalogues itself and does not depend on the process locale.

```python
import locale

locale.setlocale(locale.LC_MESSAGES, 'C')

assert locale.gettext('Hello') == 'Hello'  # no catalogue: the message comes back
assert locale.dgettext(None, 'Hello') == 'Hello'
assert locale.dcgettext(None, 'Hello', locale.LC_MESSAGES) == 'Hello'
assert locale.textdomain(None) == locale.textdomain(None)  # None only queries
```

## Common Patterns

### Switching a Category and Restoring It

The locale is process state, so a function that needs a particular locale sets it and puts the old
one back, even when the work in between raises. Other threads see the change while it lasts.

```python
import locale

def format_in(name, fmt, value):
    previous = locale.setlocale(locale.LC_NUMERIC)  # O(1)
    locale.setlocale(locale.LC_NUMERIC, name)
    try:
        return locale.format_string(fmt, value)  # O(f + r)
    finally:
        locale.setlocale(locale.LC_NUMERIC, previous)

before = locale.setlocale(locale.LC_NUMERIC)
assert format_in('C', '%.1f', 2.5) == '2.5'
assert locale.setlocale(locale.LC_NUMERIC) == before
```

## Performance Best Practices

✅ **Do**:

- Sort with `key=locale.strxfrm`, which converts each string once
- Pass `do_setlocale=False` to `getpreferredencoding()`, so it does not set `LC_CTYPE` and back
- Set the locale once, at startup, from the main thread

❌ **Avoid**:

- `functools.cmp_to_key(locale.strcoll)` as a sort key - it converts both strings on every
  comparison
- Calling `setlocale()` from worker threads - the setting is process-wide
- `grouping=True` on numbers with thousands of digits - grouping is quadratic in the digits

## Version Notes

- **Python 3.11+**: Added `getencoding()`; `getdefaultlocale()` and `resetlocale()` warn
  `DeprecationWarning`
- **Python 3.12+**: `locale.format()` is removed; use `format_string()`
- **Python 3.13+**: `resetlocale()` is removed; use `setlocale(locale.LC_ALL, '')`
- **Python 3.14.7+**: `getdefaultlocale()` no longer warns
- **All Python 3**: Which locales exist depends on what is installed; only `'C'` and `'POSIX'`
  are guaranteed

## Related Modules

- **[gettext](gettext.md)** - message translation that reads catalogues itself
- **[time](time.md)** - `strftime()` formats names in the `LC_TIME` locale
- **[string](string.md)** - `format()`'s `n` presentation type uses the `LC_NUMERIC` locale
