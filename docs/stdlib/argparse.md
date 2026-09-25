# argparse Module Complexity

The `argparse` module turns a list of command-line strings into a `Namespace` of converted values,
and writes usage, help and error messages from the same declarations. Building a parser is a
series of small registrations; the work happens in `parse_args()`, which walks the command line
and then visits every argument the parser declares, and in help formatting, which renders
text only when it is asked for.

`n` is the strings on the command line, `k` is the options among them (`-v`, `--out=x`), and `s`
is the strings that start with `-` without being an exact option spelling (see *Option
Spellings*); `a` is the arguments added to the parser, counting each option spelling
(`-v, --verbose` counts twice); `c` is the values in a `choices` container; `g` is the arguments in
one mutually exclusive group; `d` is the keyword arguments passed, or a namespace's attributes; and
`h` is the characters of help or usage text produced. A parser is assumed to declare a handful of
positional arguments, of spellings per argument and of aliases per subcommand, and few mutually
exclusive groups: each group adds O(g²) time and space to every parse, which the parsing rows leave
out. `type` conversion, the action itself, `choices` membership and comparing two attribute values
are priced at O(1) - a `choices` list is scanned, where a set or a `range` is not.

## Complexity Reference

### ArgumentParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `argparse.ArgumentParser(prog=None, usage=None, description=None, ...)` | O(1) | O(1) | Registers the built-in actions and adds `-h/--help`; `parents=[...]` adds O(a) for the parents' arguments it copies |
| `ArgumentParser.add_argument(name or flags..., **kwargs)` | O(1) | O(1) | Does not grow with the arguments already added; with `choices`, O(c) to render them into the metavar |
| `ArgumentParser.add_argument_group(title=None, description=None)` | O(1) | O(1) | Groups arguments in the help only; parsing does not see it |
| `ArgumentParser.add_mutually_exclusive_group(required=False)` | O(1) | O(1) | Every later parse builds the group's conflict table, O(g²) time and space |
| `ArgumentParser.set_defaults(**kwargs)` | O(a + d) | O(d) | Visits every argument to update a matching `dest` |
| `ArgumentParser.get_default(dest)` | O(a) | O(1) | Scans the arguments for `dest`, then the parser-level defaults |
| `ArgumentParser.register(registry_name, value, object)` | O(1) | O(1) | One dict entry; how names such as `action='store'` are resolved |
| `ArgumentParser.convert_arg_line_to_args(arg_line)` | O(1) | O(1) | Called once per line of an argument file; the default returns the line as one argument |

### Parsing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ArgumentParser.parse_args(args=None, namespace=None)` | O(a + n + n·k + a·s) | O(a + n) | Every declared argument is visited on each call, for its default and for `required`. An exact option spelling is a dict lookup; each of the s other strings costs an O(a) scan |
| `ArgumentParser.parse_known_args(args=None, namespace=None)` | O(a + n + n·k + a·s) | O(a + n) | Returns `(namespace, extras)` instead of rejecting unknown strings |
| `ArgumentParser.parse_intermixed_args(args=None, namespace=None)` | O(a + n + n·k + a·s) | O(a + n) | Positionals may appear between options; raises `TypeError` for a parser with subcommands. Before 3.12.8 and 3.13.1, both intermixed forms also render the usage line, O(a + h), on every call unless `usage` is given |
| `ArgumentParser.parse_known_intermixed_args(args=None, namespace=None)` | O(a + n + n·k + a·s) | O(a + n) | The intermixed form of `parse_known_args()` |

### Subcommands

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ArgumentParser.add_subparsers(title, description, prog, dest, required, help, metavar, ...)` | O(a) | O(a) | Renders the usage of the positionals already added into the subcommands' `prog`, unless `prog` is passed |
| `add_parser(name, aliases=(), help=None, **kwargs)` | O(1) | O(1) | Builds a new `ArgumentParser` and one dict entry per name and alias |
| Dispatching to a subcommand | O(1) | O(1) | The command name is a dict lookup however many subcommands exist; the subparser then parses the strings after it |

### Help and errors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ArgumentParser.format_help()` | O(a + h) | O(a + h) | Visits every argument, including those with `help=SUPPRESS`; rendered on each call, nothing is cached |
| `ArgumentParser.format_usage()` | O(a + h) | O(a + h) | h = characters of the usage line alone |
| `ArgumentParser.print_help(file=None)`, `ArgumentParser.print_usage(file=None)` | O(a + h) | O(a + h) | Format, then write to `sys.stdout` or `file` |
| `ArgumentParser.error(message)` | O(a + h) | O(a + h) | Prints the usage and the message to `sys.stderr`, then raises `SystemExit(2)` |
| `ArgumentParser.exit(status=0, message=None)` | O(1) | O(1) | Raises `SystemExit(status)`, after writing `message` to `sys.stderr` if given, in time linear in its length |
| `argparse.HelpFormatter`, `argparse.RawDescriptionHelpFormatter`, `argparse.RawTextHelpFormatter`, `argparse.ArgumentDefaultsHelpFormatter`, `argparse.MetavarTypeHelpFormatter` | O(1) | O(1) | Passed as `formatter_class`; a fresh formatter renders each help or usage message |

### Actions and types

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `argparse.Action(option_strings, dest, nargs=None, ...)` | O(1) | O(1) | Subclass and override `__call__(parser, namespace, values, option_string=None)` for a custom action |
| `Action.format_usage()` | O(1) | O(1) | The spelling shown in the usage line |
| `argparse.BooleanOptionalAction` | O(1) | O(1) | Adds a `--no-` spelling for each long option |
| `argparse.FileType(mode='r', bufsize=-1, encoding=None, errors=None)` | O(1) | O(1) | Opens the file when the argument is converted, during parsing; `'-'` is standard input or output |
| `argparse.ArgumentError`, `argparse.ArgumentTypeError` | O(1) | O(1) | Raise `ArgumentTypeError` from a `type` function to report a bad value |
| `argparse.SUPPRESS`, `argparse.OPTIONAL`, `argparse.ZERO_OR_MORE`, `argparse.ONE_OR_MORE`, `argparse.REMAINDER`, `argparse.PARSER` | O(1) | O(1) | String constants; the `nargs` ones decide how many strings an argument takes, not the bound |

### Namespace

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `argparse.Namespace(**kwargs)` | O(d) | O(d) | One attribute per keyword |
| `vars(namespace)` | O(1) | O(1) | The namespace's own `__dict__`, not a copy |
| `name in namespace` | O(1) | O(1) | A dict membership test |
| `namespace == other` | O(d) | O(1) | Compares the two attribute dictionaries |

## Parsing a Command Line

### Every Parse Pays for the Whole Parser

`parse_args()` starts by visiting every declared argument to put its default on the namespace,
unless the namespace already has that attribute or the default is `SUPPRESS`, and ends by visiting
every argument again for `required`, so a parser with many arguments costs O(a) even for an
empty command line. Pass the list explicitly to parse something other than `sys.argv[1:]`.

```python
import argparse

parser = argparse.ArgumentParser(prog='tool')  # O(1)
parser.add_argument('source')  # O(1)
parser.add_argument('-o', '--output', default='out.txt')  # O(1)
parser.add_argument('-v', '--verbose', action='count', default=0)
for index in range(50):
    parser.add_argument(f'--flag{index}', action='store_true')  # O(1) each

args = parser.parse_args(['data.csv', '-vv'])  # O(a + n + n·k + a·s)
assert args.source == 'data.csv' and args.verbose == 2
assert args.output == 'out.txt'  # every default is on the namespace
assert args.flag49 is False
assert len(vars(args)) == 53  # O(1) - vars() is the namespace's own dict

assert parser.get_default('output') == 'out.txt'  # O(a) scan
parser.set_defaults(output='result.txt')  # O(a + d)
assert parser.parse_args(['data.csv']).output == 'result.txt'
```

### Option Spellings

An option spelled exactly as declared, with or without `=value`, is found with a dict lookup. An
abbreviation, an unknown option, several short flags bundled into one string, a short option with
its value attached, and a negative number are instead compared against every option spelling the
parser has: these are the s strings, at O(a) each. A lone `-` and the `--` separator are not.
`allow_abbrev=False` turns off abbreviations of long options, and with them the scan for an
unknown long option, but not the bundling of short ones.

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', action='store_true')
parser.add_argument('-x', action='store_true')
parser.add_argument('-y', action='store_true')
parser.add_argument('-n', type=int)
parser.add_argument('numbers', nargs='*', type=int)

# Exact spellings, including --option=value: one dict lookup each
assert parser.parse_args(['--verbose', '-n', '3']).n == 3

# Each of these is matched by scanning the option spellings - O(a)
assert parser.parse_args(['--verb']).verbose is True  # abbreviation
args = parser.parse_args(['-xy', '-n5'])  # bundled flags, attached value
assert args.x and args.y and args.n == 5
assert parser.parse_args(['-1', '-2']).numbers == [-1, -2]  # negative numbers

strict = argparse.ArgumentParser(allow_abbrev=False, exit_on_error=False)
strict.add_argument('--verbose', action='store_true')
assert strict.parse_known_args(['--verb'])[1] == ['--verb']  # not matched
```

### Very Long Command Lines

Each option re-examines the rest of the command line to find its values, so parsing is O(n·k) in
the worst case: invisible for a typed command, reachable with an argument file of many thousands
of options. Python 3.12 and earlier also rescan every option position for each option, which
reaches the quadratic term at far smaller sizes. An `append` or `extend` action copies its list
every time the option occurs, so one option repeated r times costs O(r²); a single `nargs='*'`
option collects the same values in O(r).

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--tag', action='append', default=[])  # copies its list per occurrence
parser.add_argument('--tags', nargs='*', default=[])  # one list, filled once

repeated = parser.parse_args(['--tag', 'a', '--tag', 'b', '--tag', 'c'])  # O(r²)
collected = parser.parse_args(['--tags', 'a', 'b', 'c'])  # O(r)
assert repeated.tag == collected.tags == ['a', 'b', 'c']
assert parser.get_default('tag') == []  # the default list itself is never appended to
```

### Argument Files

With `fromfile_prefix_chars`, a string such as `@args.txt` is replaced by the file's lines before
parsing starts, one argument per line through `convert_arg_line_to_args()`. Reading the file is
linear in its size, and its arguments then count towards n and k like any others.

```python
import argparse
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / 'args.txt'
    path.write_text('--level\n3\ninput.txt\n', encoding='utf-8')

    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument('--level', type=int)
    parser.add_argument('source')

    args = parser.parse_args([f'@{path}'])  # the file becomes three arguments
    assert args.level == 3 and args.source == 'input.txt'
```

### Choices and Types

`choices` is checked with `in` for every value, and unless a `metavar` stands in for them, all of
its values are rendered when the argument is added and again into any usage or help text. A large numeric range
belongs in a `type` function, which checks a bound in O(1) and keeps the help short.

```python
import argparse

def port(text):
    value = int(text)  # O(len(text))
    if not 0 < value < 65536:
        raise argparse.ArgumentTypeError(f'{value} is not a port number')
    return value

parser = argparse.ArgumentParser(prog='serve', exit_on_error=False)
parser.add_argument('--port', type=port, default=8000)  # O(1)
parser.add_argument('--mode', choices=['fast', 'safe'])  # O(c) to render the metavar

assert parser.parse_args(['--port', '8080', '--mode', 'safe']).port == 8080
assert '{fast,safe}' in parser.format_usage()

try:
    parser.parse_args(['--port', '70000'])
except argparse.ArgumentError as error:
    assert 'not a port number' in str(error)
else:
    raise AssertionError('an out-of-range port was accepted')
```

### Mutually Exclusive Groups

A group of g arguments costs nothing to declare, but every parse lists, for each member, the
other members it conflicts with: O(g²) per call, whether or not any member is given.

```python
import argparse

parser = argparse.ArgumentParser(exit_on_error=False)
group = parser.add_mutually_exclusive_group()  # O(1)
group.add_argument('--json', action='store_true')
group.add_argument('--csv', action='store_true')

assert parser.parse_args(['--json']).json is True  # O(g²) conflict table per parse

try:
    parser.parse_args(['--json', '--csv'])
except argparse.ArgumentError as error:
    assert 'not allowed with argument' in str(error)
else:
    raise AssertionError('two exclusive options were accepted')
```

## Subcommands

Choosing a subcommand is a dict lookup, however many there are. Everything after the command name
is handed to that subparser, which parses it as its own command line, and its values are copied
onto the same namespace.

```python
import argparse

parser = argparse.ArgumentParser(prog='vcs')
subcommands = parser.add_subparsers(dest='command', required=True)  # O(a)

commit = subcommands.add_parser('commit', aliases=['ci'])  # O(1)
commit.add_argument('-m', '--message', required=True)
push = subcommands.add_parser('push')  # O(1)
push.add_argument('remote', nargs='?', default='origin')

args = parser.parse_args(['ci', '-m', 'fix'])  # dict lookup, then the subparser's parse
assert args.command == 'ci' and args.message == 'fix'

args = parser.parse_args(['push'])
assert args.command == 'push' and args.remote == 'origin'
assert not hasattr(args, 'message')  # only the chosen subparser's defaults are set
```

## Help, Usage and Errors

Help and usage text are rendered from the declarations every time they are asked for, visiting
every argument and linear in the text produced. A successful `parse_args()` renders nothing; an error renders the usage line
before exiting. With `exit_on_error=False`, a bad value raises `ArgumentError` instead.

```python
import argparse
import contextlib
import io

parser = argparse.ArgumentParser(
    prog='report',
    description='Summarise a log file.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument('path')
parser.add_argument('--limit', type=int, default=10, help='rows to show')

text = parser.format_help()  # O(a + h), rendered on each call
assert 'Summarise a log file.' in text
assert 'rows to show (default: 10)' in text  # added by ArgumentDefaultsHelpFormatter

usage = parser.format_usage()  # O(a + h) for the usage line alone
assert 'usage:' in usage and 'LIMIT' in usage
assert 'Summarise' not in usage

stderr = io.StringIO()
with contextlib.redirect_stderr(stderr):
    try:
        parser.parse_args([])  # error() prints the usage, then exits
    except SystemExit as exit:
        assert exit.code == 2
    else:
        raise AssertionError('a missing argument was accepted')
assert 'usage:' in stderr.getvalue()
assert 'the following arguments are required: path' in stderr.getvalue()
```

## Namespace

A `Namespace` is a plain attribute holder. `vars()` returns its own dictionary, so changing that
dictionary changes the namespace; equality compares every attribute.

```python
import argparse

namespace = argparse.Namespace(verbose=True, level=2)  # O(d)
assert 'level' in namespace  # O(1)

attributes = vars(namespace)  # O(1) - the live __dict__
attributes['level'] = 3
assert namespace.level == 3

assert namespace == argparse.Namespace(verbose=True, level=3)  # O(d)

# parse_args() fills a namespace you pass in instead of creating one
parser = argparse.ArgumentParser()
parser.add_argument('--level', type=int)
result = parser.parse_args(['--level', '5'], namespace=namespace)
assert result is namespace and namespace.level == 5
```

## Common Patterns

### A Testable Entry Point

Taking the argument list as a parameter keeps `sys.argv` out of the function, so the same code
path runs from the command line and from a test.

```python
import argparse

def build_parser():
    parser = argparse.ArgumentParser(prog='count')
    parser.add_argument('words', nargs='+')
    parser.add_argument('--unique', action='store_true')
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)  # argv=None reads sys.argv[1:]
    words = set(args.words) if args.unique else args.words
    return len(words)

assert main(['a', 'b', 'a']) == 3
assert main(['a', 'b', 'a', '--unique']) == 2
```

## Performance Best Practices

✅ **Do**:

- Pass the argument list to `parse_args()` in tests rather than patching `sys.argv`
- Collect many values with one `nargs='*'` or `nargs='+'` option; a repeated `append` option copies its list each time
- Validate a large numeric range in a `type` function; `choices` renders every value into the usage
- Build the parser once and reuse it; each parse still pays O(a) for its declared arguments

❌ **Avoid**:

- Argument files with many thousands of options, above all on Python 3.12 and earlier, where the quadratic term appears at far smaller sizes
- `choices=range(...)` over a wide range - O(c) when the argument is added and whenever usage is shown

## Version Notes

- **Python 3.13+**: `add_argument()` and `add_parser()` take `deprecated=True`, which warns when the argument or command is used
- **Python 3.14+**: `ArgumentParser` takes `suggest_on_error` and `color`; `FileType` is deprecated; calling `add_argument_group()` on an argument group, or `add_mutually_exclusive_group()` on a mutually exclusive group, raises `ValueError`

## Related Modules

- **[sys](sys.md)** - `sys.argv`, the list `parse_args()` reads by default
- **[optparse](optparse.md)** - the older option parser
- **[getopt](getopt.md)** - C-style option parsing without help generation
- **[shlex](shlex.md)** - split a command line string into the list `parse_args()` takes
