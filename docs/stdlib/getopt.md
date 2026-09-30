# getopt Module Complexity

The `getopt` module parses a command line the way the C `getopt()` function does: `getopt()`
stops at the first non-option argument, and `gnu_getopt()` scans the whole line so options and
positional arguments can be intermixed. It is pure Python and works on a list of strings you pass
in, usually `sys.argv[1:]`.

Arguments are the unit throughout. `n` is the arguments in `args`, `p` is the arguments the call
steps over one at a time, `s` is the characters in `shortopts`, and `k` is the entries in
`longopts`. For `getopt()`, `p` is the options and option values before the first non-option
argument; for `gnu_getopt()`, it is every argument before a `--`, or before the first non-option
in POSIX mode - when `shortopts` starts with `+`, or the `POSIXLY_CORRECT` environment variable is
non-empty. Every step slices off the rest of the list, which is where the O(p·n) term comes from;
setting up and handing back the remaining arguments cost at most one more such step, hence
`p + 1`. The bounds treat each argument and each option name as a few characters long, as
short-option clusters such as `-abc` are.

## Complexity Reference

### Parsing functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getopt.getopt(args, shortopts, longopts=[])` | O((p + 1)·(n + s + k)) | O(n + k) | Arguments from the first non-option on cost no steps: they are returned as they stand |
| `getopt.gnu_getopt(args, shortopts, longopts=[])` | O((p + 1)·(n + s + k)) | O(n + s + k) | Outside POSIX mode every argument before a `--` is a step, so a long list of positional arguments costs O(n²) |
| Looking up one short option | O(s) | O(1) | A scan of `shortopts` |
| Looking up one long option | O(k) | O(k) | Every entry of `longopts` is tested as a prefix match |

### GetoptError

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getopt.GetoptError(msg, opt='')` | O(1) | O(1) | Raised for an unknown option, a missing argument, an argument given to an option that takes none, or an ambiguous long-option prefix |
| `GetoptError.msg`, `GetoptError.opt` | O(1) | O(1) | The message, and the option it concerns without its leading dashes |
| `getopt.error` | O(1) | O(1) | An alias of `GetoptError` |

## Parsing Command-Line Arguments

A short option taking an argument is followed by `:` in `shortopts`, and a long option by `=` in
`longopts`. Each `(option, value)` pair comes back in the order given, with `''` for an option
that takes no argument.

```python
import getopt

argv = ['-v', '-o', 'out.txt', '--level=3', 'input.txt']

opts, args = getopt.getopt(argv, 'vo:', ['level='])  # O((p + 1)·(n + s + k))
assert opts == [('-v', ''), ('-o', 'out.txt'), ('--level', '3')]
assert args == ['input.txt']

# Short options can be clustered, and an argument can follow its letter directly
opts, args = getopt.getopt(['-vofile'], 'vo:')
assert opts == [('-v', ''), ('-o', 'file')]
```

### Long Option Prefixes

A long option matches any unambiguous prefix of one entry in `longopts`, so every lookup tests
all `k` entries. An exact match wins over a longer entry that shares it as a prefix.

```python
import getopt

longopts = ['foo', 'frob', 'foobar']

opts, _ = getopt.getopt(['--fr', '--foo'], '', longopts)  # O(k) per long option
assert opts == [('--frob', ''), ('--foo', '')]

try:
    getopt.getopt(['--f'], '', longopts)
except getopt.GetoptError as err:
    assert err.opt == 'f'
    assert 'not a unique prefix' in err.msg
else:
    raise AssertionError('an ambiguous prefix was accepted')
```

## Where Scanning Stops

`getopt()` stops at the first argument that is not an option, and a bare `-` counts as one. What
follows is returned as it stands, with no further steps. `gnu_getopt()` keeps going, collecting positional
arguments as it meets them, and takes one step per argument until a `--`.

```python
import getopt

argv = ['-a', 'file1', '-b', 'file2']

opts, args = getopt.getopt(argv, 'ab')  # stops at 'file1'
assert opts == [('-a', '')]
assert args == ['file1', '-b', 'file2']

opts, args = getopt.gnu_getopt(argv, 'ab')  # scans every argument
assert opts == [('-a', ''), ('-b', '')]
assert args == ['file1', 'file2']

# A leading '+' in shortopts restores getopt()'s behaviour
opts, args = getopt.gnu_getopt(argv, '+ab')
assert args == ['file1', '-b', 'file2']

# '--' ends option processing in both
opts, args = getopt.getopt(['-a', '--', '-b'], 'ab')
assert opts == [('-a', '')] and args == ['-b']
```

### Long Argument Lists

Each step replaces the remaining arguments with a slice one element shorter, so a step costs
O(n). That is harmless for a handful of options, but `gnu_getopt()` steps over positional
arguments too: a command line carrying thousands of file names costs time quadratic in their
number. A `--` in front of them hands the rest over as one slice.

```python
import getopt

files = [f'file{i}.txt' for i in range(1_000)]

# O(n²): every file name is a step, and every step copies the rest of the list
opts, args = getopt.gnu_getopt(['-v'] + files, 'v')
assert args == files

# O(n): the file names after '--' are taken in one slice
opts, args = getopt.gnu_getopt(['-v', '--'] + files, 'v')
assert opts == [('-v', '')] and args == files

# getopt() takes no step for them, since the first file name stops it
opts, args = getopt.getopt(['-v'] + files, 'v')
assert args == files
```

## Optional Arguments

From Python 3.14, `::` after a short option and `=?` after a long option make the argument
optional. An optional argument must be attached - `-ovalue` or `--color=red` - because a
separate word is never taken as the value.

```python
import getopt

opts, args = getopt.getopt(['-ow', '-o', 'value'], 'o::')
assert opts == [('-o', 'w'), ('-o', '')]
assert args == ['value']

opts, args = getopt.getopt(['--color', '--color=red'], '', ['color=?'])
assert opts == [('--color', ''), ('--color', 'red')]
```

## Keeping Arguments in Order

From Python 3.14, a `shortopts` that starts with `-` makes `gnu_getopt()` report the positional
arguments it meets between options as `(None, [arguments])` entries, so the caller sees options
and arguments in their original order. Arguments after the last option are still returned as
the second element, and the leading `-` takes precedence over `POSIXLY_CORRECT`.

```python
import getopt

argv = ['a', '-x', 'b', 'c', '--y', 'd']

opts, args = getopt.gnu_getopt(argv, '-x', ['y'])
assert opts == [(None, ['a']), ('-x', ''), (None, ['b', 'c']), ('--y', '')]
assert args == ['d']
```

## Handling Errors

Every parsing failure raises `GetoptError`. `str(err)` is its `msg`, and `opt` names the
offending option without its dashes.

```python
import getopt

try:
    getopt.getopt(['-o'], 'o:')
except getopt.GetoptError as err:
    assert err.opt == 'o'
    assert str(err) == err.msg == 'option -o requires argument'
else:
    raise AssertionError('a missing argument was accepted')

try:
    getopt.getopt(['-z'], 'o:')
except getopt.error as err:  # the same class
    assert err.opt == 'z'
    assert 'not recognized' in err.msg
else:
    raise AssertionError('an unknown option was accepted')
```

## Performance Best Practices

✅ **Do:**

- Put `--` in front of a long list of file names passed to `gnu_getopt()`, so they are taken in
  one slice instead of one O(n) step each

❌ **Avoid:**

- `gnu_getopt()` over thousands of positional arguments with no `--` - the cost is quadratic in
  their number

## Version Notes

- **Python 3.14+**: Optional arguments, with `::` in `shortopts` and `=?` in `longopts`
- **Python 3.14+**: A leading `-` in `gnu_getopt()`'s `shortopts` returns options and positional
  arguments in order
- **All Python 3**: `gnu_getopt()` stops at the first non-option argument when the
  `POSIXLY_CORRECT` environment variable is non-empty

## Related Modules

- **[argparse](argparse.md)** - declarative parsing with help and usage messages
- **[optparse](optparse.md)** - declarative option parsing that follows the same command-line conventions
- **[sys](sys.md)** - `sys.argv` supplies the list you pass in
