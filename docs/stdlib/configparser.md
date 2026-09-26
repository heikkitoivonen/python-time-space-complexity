# configparser Module Complexity

The `configparser` module reads and writes INI-style configuration: `[section]` headers followed by
`key = value` options, with a special DEFAULT section whose options every other section inherits.
The parser is pure Python and keeps the whole configuration in dictionaries, one per section, so
lookups are hash lookups; the work that is not is parsing, `%`- and `$`-interpolation when a value
is read back, and a few calls that build a list of every section or option before answering.

`c` is the characters of configuration text: the input one read call parses, the keys and values of
a dictionary handed to `read_dict()`, or the output `write()` produces. `t` is the sections and
options the parser holds after a read, DEFAULT included, `s` is sections, `o` is the options in one
section, `d` is the options in DEFAULT, and `v` is the length of one value. Interpolation adds `r`,
the references and escapes in a value, and `w`, the length of the expanded result; for an expansion,
`v`, `r` and `w` total every value it visits, the requested one and each value it pulls in. Section
and option names are priced at O(1), `optionxform()` included, and a `vars` mapping is left out of
every bound: a call given one copies it entry by entry. Each new section also gets a `SectionProxy`
that binds one getter per registered converter; the three built-in converters make that a constant.

## Complexity Reference

### ConfigParser and RawConfigParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `configparser.ConfigParser(defaults=None, dict_type=dict, allow_no_value=False, *, delimiters=('=', ':'), ..., interpolation=BasicInterpolation(), converters={})` | O(d) | O(d) | `defaults` become DEFAULT's options, converted to strings |
| `configparser.RawConfigParser(...)` | O(d) | O(d) | Same arguments; no interpolation, and `defaults` keep their types |
| `ConfigParser.read(filenames, encoding=None)` | O(c + f·t) | O(c + f) | f = files; one that cannot be opened is skipped, and the names read are returned |
| `ConfigParser.read_file(f, source=None)` | O(c + t) | O(c) | Iterates `f` a line at a time; after parsing, visits every option the parser holds, not just the new ones |
| `ConfigParser.read_string(string, source='<string>')` | O(c + t) | O(c) | `read_file()` over an `io.StringIO` |
| `ConfigParser.read_dict(dictionary, source='<dict>')` | O(c) | O(c) | One `set()` per option; does not visit the options already held |
| `ConfigParser.write(fileobject, space_around_delimiters=True)` | O(c) | O(v) | Formats and writes one option at a time; comments read in are not written back |
| `ConfigParser.get(section, option, *, raw=False, vars=None[, fallback])` | O(v·(r + 1) + w) | O(v + w + r) | Expands the value, `BasicInterpolation`'s cost shown; one with nothing to expand comes back uncopied. With `raw=True`, or on a `RawConfigParser`, O(1) |
| `ConfigParser.getint(section, option, ...)`, `ConfigParser.getfloat(...)`, `ConfigParser.getboolean(...)` | `get()` + the conversion | `get()` + the conversion | Same keywords as `get()`, then `int()`, `float()` or a `BOOLEAN_STATES` lookup |
| `ConfigParser.has_section(section)` | O(1) | O(1) | DEFAULT is not reported |
| `ConfigParser.has_option(section, option)` | O(1) | O(1) | Looks in the section, then DEFAULT; a missing section gives `False` |
| `ConfigParser.sections()` | O(s) | O(s) | A new list, DEFAULT excluded |
| `ConfigParser.options(section)` | O(o + d) | O(o + d) | Copies the section and merges DEFAULT into the copy |
| `ConfigParser.items(section, raw=False, vars=None)` | O(o + d) + one expansion per option | O(o + d) + the expanded values | A list of `(name, value)` pairs, every value expanded |
| `ConfigParser.items()` | O(1) | O(1) | A view of `(name, SectionProxy)` pairs, DEFAULT first; iterating it is O(s) |
| `ConfigParser.defaults()` | O(1) | O(1) | DEFAULT's dictionary itself, not a copy |
| `ConfigParser.set(section, option, value=None)` | O(v) | O(v) | Checks the interpolation syntax and that the value is a string; a value with nothing to expand is scanned, not copied. `RawConfigParser.set()` is O(1) and stores any value |
| `ConfigParser.add_section(section)` | O(1) | O(1) | `DuplicateSectionError` if it exists, `ValueError` for DEFAULT |
| `ConfigParser.remove_option(section, option)` | O(1) | O(1) | Returns whether the option existed |
| `ConfigParser.remove_section(section)` | O(1) | O(1) | Returns whether the section existed |
| `ConfigParser.popitem()` | O(s) | O(s) | Lists every section to take the first; DEFAULT is never removed |
| `ConfigParser.clear()` | O(s²) | O(s) | One `popitem()` per section; DEFAULT's options stay |
| `ConfigParser.readfp(fp, filename=None)` | O(c + t) | O(c) | Python 3.10 and 3.11 only; use `read_file()` |
| `configparser.SafeConfigParser(...)` | O(d) | O(d) | Python 3.10 and 3.11 only; a deprecated alias of `ConfigParser` |

### Mapping Access and SectionProxy

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `parser[section]` | O(1) | O(1) | The same `SectionProxy` every time; `KeyError` if the section is missing |
| `parser[section] = mapping` | O(o + c) | O(c) | Empties an existing section, then `read_dict()` |
| `del parser[section]` | O(1) | O(1) | `ValueError` for DEFAULT |
| `section in parser`, `len(parser)` | O(1) | O(1) | Both count DEFAULT |
| Iterating a parser | O(s) | O(1) | DEFAULT first, then the sections, lazily |
| `configparser.SectionProxy` | O(1) | O(1) | Built by the parser once per section and reused; not constructed directly |
| `SectionProxy.name`, `SectionProxy.parser` | O(1) | O(1) | Read-only |
| `SectionProxy.get(option, fallback=None, *, raw=False, vars=None, **kwargs)` | As `ConfigParser.get()` | As `ConfigParser.get()` | Returns `None` for a missing option unless given another `fallback` |
| `SectionProxy.getint(option, ...)`, `SectionProxy.getfloat(...)`, `SectionProxy.getboolean(...)` | As the parser's | As the parser's | One per converter, including those added later |
| `proxy[option]` | As `ConfigParser.get()` | As `ConfigParser.get()` | `KeyError` if missing from the section and DEFAULT |
| `proxy[option] = value` | O(v) | O(v) | `ConfigParser.set()`; a non-string value is a `TypeError` on either parser, except `None` under `allow_no_value=True` |
| `del proxy[option]` | O(1) | O(1) | `KeyError` for a name only DEFAULT supplies |
| `option in proxy` | O(1) | O(1) | `has_option()` |
| `len(proxy)`, iterating a `SectionProxy` | O(o + d) | O(o + d) | Builds `options()` first; the DEFAULT proxy iterates its dictionary directly |
| `proxy.clear()` | O((o + 1)·(o + d)) + one expansion per option | O(o + d) | One `options()` list per option removed, and each value is fetched, so expanded, first; an expansion error stops it. Names only DEFAULT supplies stay |

### Interpolation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `configparser.Interpolation()` | O(1) | O(1) | No expansion; subclass it and override `before_get`, `before_set`, `before_read` or `before_write`. `before_read` runs on every held option after each read |
| `configparser.BasicInterpolation()` | O(1) | O(1) | `%(name)s` from the same section or DEFAULT, `%%` for a percent sign; `ConfigParser`'s default |
| `configparser.ExtendedInterpolation()` | O(1) | O(1) | `${name}` or `${section:name}`, `$$` for a dollar sign |
| Expanding a `BasicInterpolation` value | O(v·(r + 1) + w) | O(v + w + r) | Each reference or escape copies the rest of the value, so many in one value are quadratic |
| Expanding an `ExtendedInterpolation` value | O(v·(r + 1) + w) + O(o + d) per nested reference | O(v + w + r + o + d) | A referenced value that itself contains `$` first copies its section's options, with DEFAULT's |
| `configparser.LegacyInterpolation()` | O(1) | O(1) | Python 3.10 to 3.12 only; deprecated |

### Converters and Customization

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ConfigParser.optionxform(optionstr)` | O(1) | O(1) | Applied to every option name read, set or looked up; lower-cases by default. Replace it before reading to keep case |
| `ConfigParser.converters` | O(1) | O(1) | The parser's `ConverterMapping` |
| `configparser.ConverterMapping` | O(1) | O(1) | Built with each parser, holding the names of its `get*()` methods; not constructed directly |
| `parser.converters[name] = func` | O(s) | O(s) | Adds `get<name>()` to the parser and to every existing `SectionProxy` |
| `ConfigParser.BOOLEAN_STATES` | O(1) | O(1) | The strings `getboolean()` accepts, matched case-insensitively |
| `ConfigParser.SECTCRE` | O(1) | O(1) | The compiled section-header pattern; override it in a subclass to change the header syntax |

### Constants and Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `configparser.DEFAULTSECT` | O(1) | O(1) | `'DEFAULT'`; `default_section=` renames it per parser |
| `configparser.MAX_INTERPOLATION_DEPTH` | O(1) | O(1) | 10; a reference chain nested deeper raises `InterpolationDepthError` |
| `configparser.UNNAMED_SECTION` | O(1) | O(1) | Python 3.13+; holds the options before the first header when `allow_unnamed_section=True` |
| `configparser.Error` | O(1) | O(1) | Base class of every exception below |
| `configparser.NoSectionError`, `configparser.NoOptionError` | O(1) | O(1) | Raised by a lookup given no `fallback` |
| `configparser.DuplicateSectionError`, `configparser.DuplicateOptionError` | O(1) | O(1) | A strict parser, the default, raises them when one source repeats a section or option |
| `configparser.ParsingError` | O(1) | O(1) | Raised once the whole input is parsed, listing every bad line in `errors`; the good lines are kept |
| `configparser.MissingSectionHeaderError` | O(1) | O(1) | Raised at the first non-blank, non-comment line before any header |
| `configparser.MultilineContinuationError` | O(1) | O(1) | Python 3.13+; an indented line after an option with no value |
| `configparser.InterpolationError`, `configparser.InterpolationMissingOptionError`, `configparser.InterpolationSyntaxError`, `configparser.InterpolationDepthError` | O(1) | O(1) | Raised when a value is expanded, not when it is read |
| `configparser.InvalidWriteError` | O(1) | O(1) | Python 3.14+; `write()` refuses a key that would read back differently |
| `configparser.UnnamedSectionDisabledError` | O(1) | O(1) | Python 3.14+; `UNNAMED_SECTION` used without `allow_unnamed_section=True` |

## Reading Configuration

### Every Read Visits the Whole Parser

Parsing is linear in the text, but a read does not stop there: once the lines are stored, the
parser walks every option it holds - in every section, including those from earlier reads - to
join multi-line values and hand each to the interpolation's `before_read` hook. Reading many small
pieces into one parser therefore costs quadratically in the number of pieces. `read_dict()` takes
the other route and never walks the existing options.

```python
import configparser

class CountingReads(configparser.Interpolation):
    def __init__(self):
        self.reads = 0

    def before_read(self, parser, section, option, value):
        self.reads += 1
        return value

hook = CountingReads()
config = configparser.ConfigParser(interpolation=hook)

config.read_dict({f'section{i}': {'key': 'value'} for i in range(100)})  # O(c)
assert hook.reads == 0

config.read_string("[extra]\nkey = value\n")  # O(c + t) - visits all 101 options
assert hook.reads == 101
```

### Bad Lines Are Collected

A line that is neither a header nor an option does not stop the parse. Every bad line is
collected, the rest of the input is still stored, and one `ParsingError` listing them all is
raised at the end. A duplicate in strict mode and an option before any header raise at once.

```python
import configparser

config = configparser.ConfigParser()
try:
    config.read_string("[app]\nname = demo\nnot an option\nport = 8080\n")  # O(c + t)
except configparser.ParsingError as error:
    assert [lineno for lineno, line in error.errors] == [3]
else:
    raise AssertionError('the bad line was accepted')
assert dict(config['app']) == {'name': 'demo', 'port': '8080'}

try:
    configparser.ConfigParser().read_string("[app]\nport = 1\nport = 2\n")
except configparser.DuplicateOptionError as error:
    assert error.lineno == 3
else:
    raise AssertionError('a repeated option was accepted')
```

## Looking Up Values

### Fallbacks and DEFAULT

A lookup checks the section, then DEFAULT. `fallback` handles a missing
option or section in the same call, so there is nothing to gain from a `has_option()` check first.

```python
import configparser

config = configparser.ConfigParser(defaults={'timeout': 30})  # O(d)
config.read_string("[server]\nport = 8080\ndebug = yes\n")

assert config.get('server', 'timeout') == '30'           # O(1) lookup - from DEFAULT, as a string
assert config.getint('server', 'port') == 8080           # get() + O(w)
assert config.getboolean('server', 'debug') is True      # 'yes' is in BOOLEAN_STATES
assert config.getint('server', 'workers', fallback=4) == 4
assert config.get('missing', 'port', fallback=None) is None

assert config.has_option('server', 'timeout')            # O(1) - DEFAULT counts
assert config.options('server') == ['port', 'debug', 'timeout']  # O(o + d) - a new list
assert config.sections() == ['server']                   # O(s) - DEFAULT excluded
```

### Section Proxies

`parser[section]` hands back the proxy the parser built for that section, and indexing it is a
`get()`. Its length and iteration are not dictionary operations: each builds the `options()` list,
DEFAULT's names included.

```python
import configparser

config = configparser.ConfigParser(defaults={'color': 'auto'})
config.read_string("[ui]\ntheme = dark\n")

ui = config['ui']                     # O(1) - the stored proxy
assert config['ui'] is ui
assert ui['theme'] == 'dark'          # a get()
assert ui.get('missing') is None      # a proxy's fallback defaults to None
assert 'color' in ui                  # O(1) - has_option()
assert len(ui) == 2                   # O(o + d) - builds options() first
assert list(ui) == ['theme', 'color']

ui['theme'] = 'light'                 # O(v) - set()
assert config.get('ui', 'theme') == 'light'
```

## Interpolation

### What an Expansion Costs

Expansion happens on every `get()`, not once at read time, so a malformed reference in text a read
parses surfaces only when the value is asked for; `set()` and `read_dict()` check the syntax at
once. `BasicInterpolation` walks the value, and each reference or `%%` escape copies the rest of
it: a few references are linear, thousands in one value are quadratic. `raw=True` skips the walk.

```python
import configparser

config = configparser.ConfigParser()
config.read_string("""
[paths]
home = /home/user
data = %(home)s/data
cache = %(data)s/cache
broken = 100%
""")  # O(c + t) - nothing is expanded yet

assert config.get('paths', 'cache') == '/home/user/data/cache'  # O(v·(r + 1) + w)
assert config.get('paths', 'cache', raw=True) == '%(data)s/cache'  # O(1)

try:
    config.get('paths', 'broken')
except configparser.InterpolationSyntaxError:
    pass
else:
    raise AssertionError('a bare % expanded')
```

### Extended Interpolation Across Sections

`ExtendedInterpolation` can reach into another section with `${section:option}`. A reference to a
plain value is a lookup, but when the referenced value contains `$` itself, the whole referenced
section, with DEFAULT, is copied into a dictionary before the nested expansion. Keep nested chains
out of large sections.

```python
import configparser

config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config.read_string("""
[common]
root = /srv
logs = ${root}/logs

[app]
log_file = ${common:logs}/app.log
""")

# ${common:logs} contains '$', so this copies the common section: O(o + d) extra
assert config['app']['log_file'] == '/srv/logs/app.log'
```

## Writing Configuration

`write()` formats and writes one option at a time, so its memory is the largest option, not the file.
It writes the values as stored - raw, with references unexpanded - and drops any comments the input
had.

```python
import configparser
import io

config = configparser.ConfigParser()
config.read_string("""
# this comment is not written back
[db]
host = localhost
url = postgres://%(host)s/app
""")

buffer = io.StringIO()
config.write(buffer)  # O(c) time, O(v) memory
assert buffer.getvalue() == '[db]\nhost = localhost\nurl = postgres://%(host)s/app\n\n'

reread = configparser.ConfigParser()
reread.read_string(buffer.getvalue())
assert reread['db']['url'] == 'postgres://localhost/app'
```

## Emptying a Parser

`clear()` is inherited from `MutableMapping` and calls `popitem()` once per section, and each
`popitem()` lists every remaining section to take the first. That makes it quadratic in the
section count. Removing the names from one `sections()` list is linear, and a fresh parser is
O(1).

```python
import configparser

config = configparser.ConfigParser(defaults={'kept': 'yes'})
config.read_dict({f'section{i}': {'key': str(i)} for i in range(1_000)})

for name in config.sections():  # O(s) - one list, then O(1) per removal
    config.remove_section(name)
assert config.sections() == []
assert config.defaults() == {'kept': 'yes'}  # DEFAULT is never removed

config.read_dict({f'section{i}': {'key': str(i)} for i in range(10)})
config.clear()  # O(s²) - fine for ten sections, not for ten thousand
assert config.sections() == [] and config.defaults() == {'kept': 'yes'}
```

## Common Patterns

### Layered Files

`read()` skips files that do not exist, so a list of candidate locations layers them: later files
override earlier ones option by option. Each file's read also walks every option held so far.

```python
import configparser
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as directory:
    base = pathlib.Path(directory, 'defaults.ini')
    local = pathlib.Path(directory, 'local.ini')
    base.write_text("[server]\nhost = 0.0.0.0\nport = 8000\n")
    local.write_text("[server]\nport = 9000\n")

    config = configparser.ConfigParser()
    missing = pathlib.Path(directory, 'absent.ini')
    loaded = config.read([base, missing, local])  # O(c + f·t)

    assert loaded == [str(base), str(local)]
    assert dict(config['server']) == {'host': '0.0.0.0', 'port': '9000'}
```

### Case-Preserving Keys and Custom Converters

```python
import configparser

config = configparser.ConfigParser(
    converters={'list': lambda value: [item.strip() for item in value.split(',')]}
)
config.optionxform = str  # keep option names as written; set before reading

config.read_string("[build]\nTargets = x86_64, arm64\n")

assert config.options('build') == ['Targets']
assert config.getlist('build', 'Targets') == ['x86_64', 'arm64']  # get() + the converter
assert config['build'].getlist('Targets') == ['x86_64', 'arm64']  # proxies get it too
```

## Performance Best Practices

✅ **Do**:

- Read a configuration once and keep the parser; lookups after that are dictionary lookups plus
  any expansion
- Pass `fallback=` rather than checking `has_option()` first
- Use `read_dict()` when merging many small sources into a big parser
- Use `raw=True`, or `RawConfigParser`, for values you do not want expanded
- Empty a parser from one `sections()` list, or replace it, rather than calling `clear()`

❌ **Avoid**:

- Reading many small strings into one parser in a loop - each read walks everything held so far
- `len()` or iteration on a `SectionProxy` inside a loop - each builds the option list again
- Thousands of references in one interpolated value - expansion copies the value per reference
- Nested `${section:option}` chains into large sections under `ExtendedInterpolation`

## Version Notes

- **Python 3.12+**: `readfp()` and `SafeConfigParser` removed; use `read_file()` and
  `ConfigParser`
- **Python 3.13+**: `LegacyInterpolation` removed; `allow_unnamed_section=True` and
  `UNNAMED_SECTION` accept options before the first header; `MultilineContinuationError` added
- **Python 3.14+**: `write()` raises `InvalidWriteError` for a key containing a delimiter or
  matching the section-header pattern; `UnnamedSectionDisabledError` added

## Related Modules

- **[tomllib](tomllib.md)** - read-only TOML parsing, with typed values instead of strings
- **[json](json.md)** - O(n) parsing for nested data
- **[io](io.md)** - `StringIO` for in-memory configuration text
