# optparse Module Complexity

The `optparse` module parses command-line options declared up front on an `OptionParser`. It is
pure Python: each registered option string is a dictionary key, and `parse_args()` walks the
argument list once, consuming options and their values from the front. `argparse` is the
documented recommendation for new applications; `optparse` remains supported and gives
lower-level control over how options and positional arguments interleave.

`a` is the argument strings handed to `parse_args()`, `o` is the options registered on the parser
(its groups included), `d` is the entries in the parser's defaults (one per destination, plus any
from `set_defaults()`), `L` is the long option strings registered, `c` is the choices of one
`choice` option, and `h` is the characters of help output. Checking a `choice` value costs O(c)
wherever it happens, on the command line or in a string default. Strings the caller supplies -
option strings, arguments, usage, messages - are priced at O(1) each, except that help text
counts toward `h` and a cluster of short flags such as `-vvv` costs one step per flag; a
callback's own cost is excluded.

## Complexity Reference

### OptionParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `optparse.OptionParser(usage=None, option_list=None, option_class=Option, version=None, conflict_handler='error', description=None, formatter=None, add_help_option=True, prog=None, epilog=None)` | O(o) | O(o) | Registers `option_list`, `standard_option_list` and the `--help`/`--version` options |
| `OptionParser.add_option(*opt_str, **attrs)`, `OptionParser.add_option(option)` | O(1) | O(1) | Attributes are validated when the `Option` is built, not when it is parsed; a resolved conflict that leaves an earlier option with no strings removes it from its list in O(o) |
| `OptionParser.add_options(option_list)` | O(k) | O(k) | k = options added; one `add_option` each |
| `OptionParser.get_option(opt_str)`, `OptionParser.has_option(opt_str)` | O(1) | O(1) | Exact option strings only; abbreviations are resolved by `parse_args()` alone |
| `OptionParser.remove_option(opt_str)` | O(o) | O(1) | Removes the option from its container's list by a linear scan |
| `OptionParser.set_default(dest, value)` | O(1) | O(1) | One dict entry |
| `OptionParser.set_defaults(**kwargs)` | O(k) | O(k) | k = keyword arguments |
| `OptionParser.get_default_values()` | O(o + d) | O(o + d) | Copies the defaults and converts each string default through its option's type checker |
| `OptionParser.set_usage(usage)`, `OptionParser.set_conflict_handler(handler)`, `OptionParser.set_description(description)`, `OptionParser.set_process_default_values(process)` | O(1) | O(1) | Attribute updates |
| `OptionParser.enable_interspersed_args()`, `OptionParser.disable_interspersed_args()` | O(1) | O(1) | Disabled, parsing stops at the first positional argument and returns the rest untouched |
| `OptionParser.standard_option_list` | O(1) | O(1) | Class attribute; its options are added when each parser is built |
| `OptionParser.destroy()` | O(g) | O(1) | g = option groups; breaks reference cycles, after which the parser is unusable |

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OptionParser.parse_args(args=None, values=None)` | O(o + d + a²) | O(o + d + a) | Each consumed argument is removed from the front of the remaining list, which is the a² term; an abbreviated long option adds O(L) and a `choice` value O(c). Passing `values` skips the O(o + d) defaults |
| Arguments left after `--`, or after the first positional with interspersed arguments disabled | O(a) | O(a) | Parsing stops there; the remainder is copied into the returned list, not consumed one at a time |
| `OptionParser.check_values(values, args)` | O(1) | O(1) | Hook called with the result; returns its arguments unchanged unless overridden |
| `OptionParser.largs`, `OptionParser.rargs`, `OptionParser.values` | O(1) | O(1) | The parse's live state, for callbacks |

### Option

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `optparse.Option(*opt_str, **attrs)`, `optparse.make_option(*opt_str, **attrs)` | O(1) | O(1) | Raises `OptionError` for an invalid combination of attributes |
| `Option.action`, `Option.type`, `Option.dest`, `Option.default`, `Option.nargs`, `Option.const`, `Option.choices`, `Option.callback`, `Option.callback_args`, `Option.callback_kwargs`, `Option.help`, `Option.metavar` | O(1) | O(1) | Attributes, set from the keyword arguments |
| `Option.check_value(opt, value)`, `Option.convert_value(opt, value)` | O(1) per value | O(1) per value | O(c) for `choice`, which scans the choices sequence |
| `Option.process(opt, value, values, parser)`, `Option.take_action(action, dest, opt, value, values, parser)` | O(1) | O(1) | Plus `process()`'s value conversion, the callback for `action='callback'`, and the help output for `help` and `version`; `append` grows one list, amortized O(1) |
| `Option.takes_value()`, `Option.get_opt_string()` | O(1) | O(1) | |
| `optparse.check_choice(option, opt, value)`, `optparse.check_builtin(option, opt, value)` | O(c), O(1) | O(1) | The type checkers for `choice` and the numeric types |

### Values

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `optparse.Values(defaults=None)` | O(d) | O(d) | One attribute per default |
| `Values.ensure_value(attr, value)` | O(1) | O(1) | Sets the attribute when it is missing or `None`; what `append` and `count` build on |

### OptionGroup

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `optparse.OptionGroup(parser, title, description=None)` | O(1) | O(1) | Shares the parser's option dicts, so an option string is unique across every group |
| `OptionParser.add_option_group(title, description=None)`, `OptionParser.add_option_group(group)` | O(1) | O(1) | |
| `OptionParser.get_option_group(opt_str)` | O(1) | O(1) | The group holding the option, or `None` for one on the parser itself |
| `OptionGroup.add_option(...)`, `OptionGroup.set_title(title)`, `OptionGroup.destroy()` | O(1) | O(1) | As on the parser |
| `optparse.OptionContainer` | O(1) | O(1) | Base class of `OptionParser` and `OptionGroup` |

### Help and usage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `OptionParser.format_help(formatter=None)`, `OptionParser.print_help(file=None)` | O(o + h) | O(o + h) | The whole text is built as one string before it is written |
| `OptionParser.format_option_help(formatter=None)` | O(o + h) | O(o + h) | The option listing `format_help()` includes |
| `OptionParser.format_description(formatter)`, `OptionParser.format_epilog(formatter)`, `OptionParser.get_usage()`, `OptionParser.print_usage(file=None)`, `OptionParser.get_version()`, `OptionParser.print_version(file=None)` | O(h) | O(h) | `%prog` is replaced by the program name everywhere but the epilog |
| `OptionParser.get_prog_name()`, `OptionParser.expand_prog_name(s)`, `OptionParser.get_description()` | O(h) | O(h) | The name is `prog`, or the basename of `sys.argv[0]` |
| `OptionParser.error(msg)` | O(h) | O(h) | Prints the usage and `msg` to stderr, then raises `SystemExit(2)` |
| `OptionParser.exit(status=0, msg=None)` | O(1) | O(1) | Raises `SystemExit` |
| `optparse.HelpFormatter`, `optparse.IndentedHelpFormatter(indent_increment=2, max_help_position=24, width=None, short_first=1)`, `optparse.TitledHelpFormatter(indent_increment=0, max_help_position=24, width=None, short_first=0)` | O(1) | O(1) | With `width=None` the width comes from `$COLUMNS` |

### Constants and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `optparse.SUPPRESS_HELP`, `optparse.SUPPRESS_USAGE` | O(1) | O(1) | Sentinels that leave an option out of the help, or drop the usage line |
| `optparse.OptParseError` | O(1) | O(1) | Base class of every exception below |
| `optparse.OptionError`, `optparse.OptionConflictError` | O(1) | O(1) | Raised while options are declared: an invalid attribute, or an option string already taken |
| `optparse.BadOptionError`, `optparse.AmbiguousOptionError`, `optparse.OptionValueError` | O(1) | O(1) | Raised while parsing; `parse_args()` turns them into `error()` |

## Parsing a Command Line

### Basic Option Parsing

Registering an option is a dictionary entry per option string, and `parse_args()` reads the
arguments you pass it, or `sys.argv[1:]` when you pass nothing.

```python
import optparse

parser = optparse.OptionParser(prog='tool')  # O(o) - only --help so far
parser.add_option('-f', '--file', dest='filename')  # O(1)
parser.add_option('-v', '--verbose', action='store_true', default=False)  # O(1)
parser.add_option('-n', type='int', default=1)  # O(1)

options, args = parser.parse_args(['-v', '--file=in.txt', '-n', '3', 'extra'])  # O(o + d + a²)
assert options.filename == 'in.txt'
assert options.verbose is True
assert options.n == 3
assert args == ['extra']
```

### Long Argument Lists

Every argument `parse_args()` consumes is deleted from the front of the list it is still walking,
so a long list of positional arguments costs quadratic time. `--` ends option processing, and the
arguments after it are handed back without being consumed; so does the first positional argument
once interspersed arguments are disabled.

```python
import optparse

files = [f'file{i}.txt' for i in range(1_000)]

parser = optparse.OptionParser()
parser.add_option('-v', action='count', default=0)

# Mixed in with the options: every file is consumed one by one - O(a²)
options, args = parser.parse_args(['-v'] + files)
assert args == files

# After '--': parsing stops, the rest is copied - O(a)
options, args = parser.parse_args(['-v', '--'] + files)
assert args == files and options.v == 1

# Interspersed arguments disabled: parsing stops at the first positional - O(a)
parser.disable_interspersed_args()  # O(1)
options, args = parser.parse_args(['-v'] + files + ['-v'])
assert options.v == 1 and args[-1] == '-v'
```

### Abbreviated Long Options

An exact long option costs O(1) dictionary lookups. An abbreviation such as `--verb` is matched against
every registered long option string, O(L), and a prefix that fits more than one is an error.

```python
import optparse

class RaisingParser(optparse.OptionParser):
    def error(self, msg):
        raise ValueError(msg)

parser = RaisingParser()
parser.add_option('--verbose', action='store_true')
parser.add_option('--version-file')

options, _ = parser.parse_args(['--verbose'])  # lookup O(1) - exact match
assert options.verbose is True
options, _ = parser.parse_args(['--verb'])  # lookup O(L) - scans the long options
assert options.verbose is True

try:
    parser.parse_args(['--ver'])  # lookup O(L) - fits both
except ValueError as error:
    assert 'ambiguous option' in str(error)
else:
    raise AssertionError('an ambiguous prefix was accepted')

assert parser.get_option('--verb') is None  # O(1) - exact strings only
```

## Option Types and Actions

Each value is converted when it is consumed. The numeric types are one conversion, and `choice`
scans its choices sequence, O(c). `append` grows one list per destination; a callback runs once
per occurrence, at its own cost.

```python
import optparse

parser = optparse.OptionParser()
parser.add_option('--mode', type='choice', choices=['fast', 'safe'])  # O(c) per value
parser.add_option('-I', dest='include', action='append')  # amortized O(1) per value
parser.add_option('-q', action='count', dest='quiet')  # O(1) per occurrence
seen = []
parser.add_option('--mark', action='callback', callback=lambda *args: seen.append(args[1]))

options, _ = parser.parse_args(['--mode', 'safe', '-I', 'a', '-I', 'b', '-qq', '--mark'])
assert options.mode == 'safe'
assert options.include == ['a', 'b']
assert options.quiet == 2
assert seen == ['--mark']

# A bad value is caught at declaration or parse time, not later
try:
    optparse.Option('--x', type='choice')  # O(1) - validated when declared
except optparse.OptionError as error:
    assert 'must supply a list of choices' in str(error)
else:
    raise AssertionError('a choice option without choices was accepted')
```

### Defaults

Every `parse_args()` call without a `values` argument builds a fresh `Values` from the parser's
defaults, O(o + d). Passing your own `Values` skips that step and fills it in place.

```python
import optparse

parser = optparse.OptionParser()
parser.add_option('-n', type='int', default='5')  # a string default is converted
parser.set_defaults(level='info')  # O(k)

defaults = parser.get_default_values()  # O(o + d)
assert defaults.n == 5 and defaults.level == 'info'

values = optparse.Values({'n': 0})  # O(d)
options, _ = parser.parse_args(['-n', '7'], values=values)  # skips the defaults
assert options is values and values.n == 7
assert not hasattr(values, 'level')
```

## Option Groups

A group is a heading in the help output and nothing more for parsing: it shares its parser's
option dictionaries, so adding to a group costs the same as adding to the parser, and an option
string cannot appear in two groups.

```python
import optparse

parser = optparse.OptionParser()
group = parser.add_option_group('Debug')  # O(1)
group.add_option('--trace', action='store_true')  # O(1), into the parser's dicts

assert parser.has_option('--trace')  # O(1)
assert parser.get_option_group('--trace') is group  # O(1)

try:
    parser.add_option('--trace')
except optparse.OptionConflictError as error:
    assert 'conflicting option string' in str(error)
else:
    raise AssertionError('a duplicate option string was accepted')
```

## Removing Options

Removing an option deletes its strings from the dictionaries in O(1), but also deletes the option
from its container's list, which is a linear scan.

```python
import optparse

parser = optparse.OptionParser()
parser.add_option('-a', '--alpha')
parser.add_option('-b', '--beta')

parser.remove_option('--alpha')  # O(o)
assert not parser.has_option('-a') and not parser.has_option('--alpha')

try:
    parser.remove_option('--alpha')
except ValueError as error:
    assert 'no such option' in str(error)
else:
    raise AssertionError('a removed option was removed again')
```

## Help Output

`format_help()` walks every option, wraps each help string, and joins the result into one string;
`print_help()` writes that string in a single call. A fixed `width` makes the output independent of
`$COLUMNS`.

```python
import io
import optparse

formatter = optparse.IndentedHelpFormatter(width=60)  # O(1)
parser = optparse.OptionParser(prog='tool', usage='%prog [options] FILE', formatter=formatter)
parser.add_option('-n', type='int', default=3, help='retries [default: %default]')

text = parser.format_help()  # O(o + h)
assert text.startswith('Usage: tool [options] FILE\n')
assert 'retries [default: 3]' in text

buffer = io.StringIO()
parser.print_help(buffer)  # O(o + h) - one write
assert buffer.getvalue() == text
```

## Common Patterns

### Raising Instead of Exiting

`parse_args()` reports every bad option through `error()`, which exits the process. Overriding it
is the documented way to keep control.

```python
import optparse

class RaisingParser(optparse.OptionParser):
    def error(self, msg):
        raise ValueError(msg)

parser = RaisingParser()
parser.add_option('-n', type='int')

try:
    parser.parse_args(['-n', 'many'])
except ValueError as error:
    assert "invalid integer value: 'many'" in str(error)
else:
    raise AssertionError('a non-integer was accepted')
```

### Forwarding Options to a Subcommand

```python
import optparse

parser = optparse.OptionParser()
parser.add_option('-v', action='store_true')
parser.disable_interspersed_args()  # stop at the subcommand

options, args = parser.parse_args(['-v', 'run', '-v', '--fast'])  # O(o + d + a)
assert options.v is True
assert args == ['run', '-v', '--fast']  # left for the subcommand's own parser
```

## Performance Best Practices

✅ **Do**:

- Put `--` before a long list of positional arguments, or disable interspersed arguments, so they
  are copied rather than consumed one at a time
- Spell long options out in scripts; an abbreviation scans every long option string
- Override `error()` to raise when parsing is not the program's own command line

❌ **Avoid**:

- Long lists of positional arguments mixed in with options: that is the O(a²) path
- Calling `remove_option()` in a loop over a large parser; each call scans the option list
- Expecting `get_option()` or `has_option()` to accept an abbreviation

## Version Notes

- **All Python 3**: `parse_args()` exits the process with status 2 on a bad option or value;
  override `error()` to raise instead

## Related Modules

- **[argparse](argparse.md)** - the recommended parser for new applications, with subcommands and
  positional argument declarations
- **[getopt](getopt.md)** - the C-style procedural parser `optparse` replaces
- **[shlex](shlex.md)** - split a command string into the argument list `parse_args()` takes
