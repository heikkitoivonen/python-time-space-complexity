# string Module Complexity

The `string` module holds the ASCII character-class constants, `capwords()`, and two ways of
filling text with values: `$`-style `Template` substitution and `Formatter`, a subclassable
Python version of `str.format()`. From Python 3.14 its `string.templatelib` submodule holds the types that
t-string literals evaluate to. Nothing here caches a parse: `Template` and `Formatter` walk the
string again on every call.

`n` is the characters in the input string (the template, the format string, or the text being
processed), `p` is its placeholders (replacement fields, or interpolations for a t-string), `u` is
its distinct placeholder names, `k` is the characters in one field name, `v` is the characters all substituted values produce as text, and
`w` is the characters one value produces. `a` is the arguments passed to a
`templatelib.Template`. Mapping lookups and attribute access are O(1), and a `$` placeholder
name counts as O(1) to copy or compare; producing a value's text (`str()`, `repr()`, `format()`)
is priced by the characters it produces.

## Complexity Reference

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `string.ascii_letters`, `string.ascii_lowercase`, `string.ascii_uppercase` | O(1) | O(1) | Module-level `str` objects of fixed length |
| `string.digits`, `string.hexdigits`, `string.octdigits` | O(1) | O(1) | Module-level `str` objects of fixed length |
| `string.punctuation`, `string.whitespace`, `string.printable` | O(1) | O(1) | `printable` is digits, letters, punctuation and whitespace together |

### capwords

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `string.capwords(s, sep=None)` | O(n) | O(n) | Splits, capitalizes each word and joins; with `sep=None` runs of whitespace become one space and the ends are stripped |

### Template

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `string.Template(template)` | O(1) | O(1) | Stores the string; nothing is parsed until a method runs |
| `Template.substitute(mapping={}, /, **kwds)` | O(n + v) | O(n + v) | Scans the whole template on every call; raises `KeyError` for a missing name and `ValueError` for a malformed placeholder; keywords take precedence over `mapping` |
| `Template.safe_substitute(mapping={}, /, **kwds)` | O(n + v) | O(n + v) | Leaves missing and malformed placeholders in the result instead of raising |
| `Template.is_valid()` | O(n) | O(1) | Python 3.11+; `False` if any placeholder is malformed |
| `Template.get_identifiers()` | O(n + p·u) | O(u) | Python 3.11+; names in first-seen order, each checked against a list of the names already found |
| `Template.template` | O(1) | O(1) | The string passed in; reassigning it changes what the next call scans |
| `Template.delimiter`, `Template.idpattern`, `Template.braceidpattern`, `Template.flags` | O(1) | O(1) | Class attributes a subclass overrides; they are compiled into its `pattern` when the subclass is defined |
| `Template.pattern` | O(1) | O(1) | The compiled regular expression, shared by every instance of the class; no call recompiles it |

### Formatter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `string.Formatter()` | O(1) | O(1) | Holds no state; subclass it to override the methods below |
| `Formatter.format(format_string, /, *args, **kwargs)` | O(n + v) | O(n + v) | Does what `str.format()` does, but the loop over fields runs in Python rather than C, so it is the slower of the two |
| `Formatter.vformat(format_string, args, kwargs)` | O(n + v) | O(n + v) | What `format()` calls; collects the arguments used and passes them to `check_unused_args()` once |
| `Formatter.parse(format_string)` | O(1) | O(1) | Returns a lazy iterator; walking it is O(n) in total, and a malformed field raises only when reached |
| `Formatter.get_field(field_name, args, kwargs)` | O(k) | O(k) | One lookup per `.name` or `[index]` in the field name |
| `Formatter.get_value(key, args, kwargs)` | O(1) | O(1) | `args[key]` for an integer key, `kwargs[key]` otherwise |
| `Formatter.convert_field(value, conversion)` | O(w) | O(w) | `str()`, `repr()` or `ascii()` for `!s`, `!r`, `!a`; O(1) with no conversion, when the value is returned as it is |
| `Formatter.format_field(value, format_spec)` | O(w) | O(w) | `format(value, format_spec)` |
| `Formatter.check_unused_args(used_args, args, kwargs)` | O(1) | O(1) | Does nothing unless overridden |

### templatelib (Python 3.14+)

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Evaluating a t-string literal `t"..."` | O(p) | O(p) | Evaluates every expression; the interpolated values are neither converted nor formatted, though fields nested in a format spec are |
| `string.templatelib.Template(*args)` | O(a) | O(a) | When strings and interpolations alternate, as a literal produces them; consecutive strings are joined one concatenation at a time, which is quadratic in the number of strings joined |
| `templatelib.Template.strings`, `templatelib.Template.interpolations` | O(1) | O(1) | Tuples stored on the template, the same object on every access |
| `templatelib.Template.values` | O(p) | O(p) | Built from the interpolations on every access |
| Iterating a `templatelib.Template` | O(p) | O(1) | Strings and interpolations in order, empty strings skipped |
| `templatelib.Template + templatelib.Template` | O(p) | O(p) | Copies both operands' parts into a new template, plus the characters of the two strings that meet; adding a `str` raises `TypeError` |
| `string.templatelib.Interpolation(value, expression='', conversion=None, format_spec='')` | O(1) | O(1) | Stores its arguments |
| `Interpolation.value`, `Interpolation.expression`, `Interpolation.conversion`, `Interpolation.format_spec` | O(1) | O(1) | Stored attributes |
| `string.templatelib.convert(obj, /, conversion)` | O(w) | O(w) | `str()`, `repr()` or `ascii()` for `'s'`, `'r'`, `'a'`; `obj` unchanged for `None` |

## Character Constants

The constants are ordinary strings of fixed length, so reading one is O(1) and testing a character
against one is O(1) too. Filtering text by them is a single O(n) pass.

```python
import secrets
import string

assert string.hexdigits == string.digits + 'abcdefABCDEF'
assert string.printable == (
    string.digits + string.ascii_letters + string.punctuation + string.whitespace
)

text = 'abc123def456'
digits = ''.join(c for c in text if c in string.digits)  # O(n)
letters = ''.join(c for c in text if c in string.ascii_letters)  # O(n)
assert (digits, letters) == ('123456', 'abcdef')

# secrets, not random, for anything that guards access
alphabet = string.ascii_letters + string.digits
token = ''.join(secrets.choice(alphabet) for _ in range(16))  # O(length)
assert len(token) == 16 and set(token) <= set(alphabet)
```

## Capitalizing Words

`capwords()` is `split()`, `capitalize()` on each word, and `join()`: three linear passes. Unlike
`str.title()`, which starts a new word after any uncased character such as an apostrophe, it
capitalizes only what follows the separator.

```python
from string import capwords

assert capwords('  hello   wORLD ') == 'Hello World'  # O(n) - whitespace collapses
assert capwords("don't stop") == "Don't Stop"
assert "don't stop".title() == "Don'T Stop"

# An explicit separator is kept as it is, empty words included
assert capwords('hello--world', sep='-') == 'Hello--World'  # O(n)
```

## Template Strings

### Substitution Scans Every Call

Building a `Template` stores the string and nothing else. Each `substitute()` or
`safe_substitute()` scans the whole template with the class's compiled pattern, so reusing one
`Template` object saves no parsing: the pattern is the only thing shared between calls.

```python
from string import Template

template = Template('$name is $age years old')  # O(1) - nothing is parsed yet

assert template.substitute(name='Alice', age=30) == 'Alice is 30 years old'  # O(n + v)
assert template.substitute({'name': 'Bob', 'age': 25}) == 'Bob is 25 years old'  # O(n + v)

# Keywords take precedence over the mapping
assert template.substitute({'name': 'Bob', 'age': 25}, age=26) == 'Bob is 26 years old'

# The next call scans whatever the template now holds
template.template = 'Hi $name'
assert template.substitute(name='Cara') == 'Hi Cara'
```

### Missing and Malformed Placeholders

`substitute()` raises at the first placeholder it cannot fill; `safe_substitute()` copies it into
the result and carries on. `$$` is a literal `$` in both.

```python
from string import Template

template = Template('Total: $$${amount} for $item')

assert template.safe_substitute(amount='29.99') == 'Total: $29.99 for $item'  # O(n + v)

try:
    template.substitute(amount='29.99')
except KeyError as error:
    assert error.args == ('item',)
else:
    raise AssertionError('a missing name was substituted')

try:
    Template('costs $ 5').substitute()
except ValueError as error:
    assert 'Invalid placeholder' in str(error)
else:
    raise AssertionError('a bare $ was accepted')
```

### Checking and Listing Placeholders

`is_valid()` and `get_identifiers()` (Python 3.11+) scan the template the way `substitute()` does,
without substituting. `get_identifiers()` checks each name against a list of those already found,
so a template with thousands of distinct names costs quadratic time; a dictionary keyed by name
keeps the same first-seen order in one pass.

```python
from string import Template

template = Template('$user logged in from $host; ${user} again')

assert template.is_valid()  # O(n)
assert not Template('costs $ 5').is_valid()
assert template.get_identifiers() == ['user', 'host']  # O(n + p·u)

# The same names in O(n + p), for templates with many distinct names
names = dict.fromkeys(
    match['named'] or match['braced']
    for match in Template.pattern.finditer(template.template)
    if match['named'] or match['braced']
)
assert list(names) == ['user', 'host']
```

### Custom Delimiters

A subclass changes the syntax through class attributes. They are compiled into the subclass's
`pattern` once, when the class statement runs, and every instance and call then shares it.

```python
import re
from string import Template

class PercentTemplate(Template):
    delimiter = '%'

assert isinstance(PercentTemplate.pattern, re.Pattern)  # compiled with the class
assert PercentTemplate('%who owes %%5').substitute(who='Bob') == 'Bob owes %5'  # O(n + v)
```

## Formatter

### Formatter vs str.format

`Formatter` produces what `str.format()` produces, through the same C parser, but walks the fields
in a Python loop and calls a method per step. Before Python 3.14 it also rejects an unnumbered
field that goes on to an attribute or index, such as `{.real}`, which `str.format()` accepts. That loop makes it the slower choice when you need
nothing but the output; its reason to exist is subclassing, where overriding one method changes
how every field is looked up, converted or formatted.

```python
from string import Formatter

formatter = Formatter()  # O(1)
assert formatter.format('{0} {1}', 'Hello', 'World') == 'Hello World'  # O(n + v)
assert formatter.format('{name}: {value:.2f}', name='Price', value=19.99) == 'Price: 19.99'
assert formatter.vformat('{x}-{y}', (), {'x': 1, 'y': 2}) == '1-2'  # O(n + v)

class Defaulting(Formatter):
    def get_value(self, key, args, kwargs):  # O(1) per field
        if isinstance(key, str):
            return kwargs.get(key, '?')
        return super().get_value(key, args, kwargs)

assert Defaulting().format('{a} and {b}', a=1) == '1 and ?'
```

### Walking a Format String

`parse()` returns an iterator, not a list: each step yields one
`(literal_text, field_name, format_spec, conversion)` tuple, and a malformed field raises only when
iteration reaches it.

```python
from string import Formatter

formatter = Formatter()
pieces = list(formatter.parse('{name}: {value:.2f}!'))  # O(n) to exhaust
assert pieces == [('', 'name', '', None), (': ', 'value', '.2f', None), ('!', None, None, None)]

steps = formatter.parse('fine {0} then {')  # O(1) - nothing is parsed yet
assert next(steps) == ('fine ', '0', '', None)
try:
    next(steps)
except ValueError as error:
    assert "Single '{'" in str(error)
else:
    raise AssertionError('a lone brace was parsed')

# The hooks format() goes through, one call per field
point = complex(3, 4)
assert formatter.get_field('0.imag', (point,), {}) == (4.0, 0)  # O(k)
assert formatter.convert_field('x', 'r') == "'x'"  # O(w)
assert formatter.format_field(3.14159, '.2f') == '3.14'  # O(w)
```

## Template String Literals

A t-string literal (Python 3.14+) evaluates its expressions immediately but does not convert or
format the interpolated values; only fields nested in a format spec are formatted. The result is a `string.templatelib.Template` holding the literal strings and one
`Interpolation` per field. Rendering it is up to the code that receives it, which is where the
O(v) cost of producing text is paid.

```python
from string.templatelib import Interpolation, Template, convert

name, width = 'Ada', 6
template = t'Hello {name!r:>{width}}!'  # O(p) - name is not converted or formatted yet

assert template.strings == ('Hello ', '!')  # O(1)
assert template.values == ('Ada',)  # O(p) - a new tuple each time
field = template.interpolations[0]
assert (field.expression, field.conversion, field.format_spec) == ('name', 'r', '>6')

def render(template):
    parts = []
    for item in template:  # O(p)
        if isinstance(item, Interpolation):
            value = convert(item.value, item.conversion)  # O(w)
            parts.append(format(value, item.format_spec))  # O(w)
        else:
            parts.append(item)
    return ''.join(parts)

assert render(template) == "Hello  'Ada'!"  # O(n + v)

# Built by hand, strings and interpolations alternate
built = Template('x = ', Interpolation(42, 'x'), '')  # O(a)
assert render(built) == 'x = 42'
```

### Combining Templates

`+` builds a new template from both operands' parts, so it costs the size of the result, and it
accepts only another template. Growing one template with `+=` in a loop therefore copies
everything accumulated so far on each step. Collect the parts in a list and build the template once
instead, alternating strings and interpolations so no strings need joining.

```python
from string.templatelib import Interpolation, Template

greeting = t'Hi {"Ada"}' + t', from {"Bob"}'  # O(p)
assert greeting.strings == ('Hi ', ', from ', '')

try:
    greeting + '!'
except TypeError as error:
    assert 'can only concatenate' in str(error)
else:
    raise AssertionError('a str was added to a Template')

parts = []
for index in range(3):
    parts += [f'item {index}: ', Interpolation(index, 'index')]
listing = Template(*parts)  # O(a) - once, not per item
assert listing.values == (0, 1, 2)
```

## Common Patterns

### Filling a Message Template

```python
from string import Template

MESSAGE = Template('Dear $name,\nThank you for buying $item.\nTotal: $$${amount}\n')

def render_message(fields):
    return MESSAGE.substitute(fields)  # O(n + v)

text = render_message({'name': 'Alice', 'item': 'Book', 'amount': '29.99'})
assert text.endswith('Total: $29.99\n')
```

### Substituting Settings Into a Config File

```python
import io
from string import Template

source = io.StringIO('host = $HOST\nport = ${PORT}\nkeep = $UNSET\n')
settings = {'HOST': 'localhost', 'PORT': 8080}

config = Template(source.read()).safe_substitute(settings)  # O(n + v)
assert config == 'host = localhost\nport = 8080\nkeep = $UNSET\n'
```

## Performance Best Practices

✅ **Do**:

- Use `str.format()` when you need only the output; keep `Formatter` for overriding its methods
- Build a t-string template from a list of alternating strings and interpolations in one call
- Collect distinct names with a dictionary over `Template.pattern.finditer()` when a template has
  thousands of them

❌ **Avoid**:

- Expecting a reused `Template` or `Formatter` to skip parsing: every call scans the string again
- `get_identifiers()` on templates with thousands of distinct names, which is quadratic in them
- `+=` on a `templatelib.Template` in a loop, which copies everything accumulated on each step
- Passing long runs of consecutive strings to `templatelib.Template()`; join them first

## Version Notes

- **Python 3.11+**: Added `Template.is_valid()` and `Template.get_identifiers()`
- **Python 3.14+**: Added `string.templatelib` and t-string literals
- **Python 3.14+**: `Formatter` accepts `{.name}` and `{[index]}` in automatically numbered fields, as `str.format()` does; earlier versions raise `KeyError`

## Related Modules

- **[str](../builtins/str.md)** - `str.format()`, `str.title()` and the string methods these build on
- **[re](re.md)** - the regular expressions `Template.pattern` is compiled with
- **[textwrap](textwrap.md)** - wrapping and indenting text once it is filled in
- **[secrets](secrets.md)** - choosing random characters from these constants for tokens
