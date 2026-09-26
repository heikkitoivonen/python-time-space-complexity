# shlex Module Complexity

The `shlex` module tokenizes shell-like text and quotes strings for a POSIX shell. The lexer is
pure Python, reads one character at a time and stops once it has a token; `split()` runs it to the
end and collects every token into a list, while `quote()` and `join()` go the other way.

`n` is the characters in the input - the string passed to `split()`, `quote()`, `shlex()` or
`push_source()`, all arguments together for `join()` - and `a` is the arguments `join()` is given.
`k` is the characters in one token, and `Σk²` sums over the tokens produced. `c` is the characters
one call reads, including the whitespace and comments it skips, and `m` is the longest comment line
it skips. The lexer's character classes (`wordchars`, `whitespace`, `quotes`, `punctuation_chars`
and the rest) are treated as fixed-size, and file names and line numbers are priced at O(1). The
lexer bounds cover one source: popping an exhausted pushed source adds O(1) per source, and with
`source` set a call may also read an inclusion's keyword and file-name tokens and the file it
opens.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shlex.split(s, comments=False, posix=True)` | O(n + Σk²) | O(n) | Linear while tokens stay short; one n-character token is O(n²) |
| `shlex.quote(s)` | O(n) | O(n) | Returns a non-empty `s` itself when every character is shell-safe; otherwise wraps it in single quotes |
| `shlex.join(split_command)` | O(n + a) | O(n + a) | One `quote()` per argument, joined with spaces |

### shlex

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shlex.shlex(instream=None, infile=None, posix=False, punctuation_chars=False)` | O(1); O(n) for a `str` | O(1); O(n) for a `str` | A stream is read lazily; a `str` is first copied into a `StringIO`. With no `instream` the lexer reads `sys.stdin` |
| `shlex.get_token()` | O(c + k²) | O(k + m) | O(1) when a pushed-back token is waiting; a skipped comment is read as one line |
| `shlex.read_token()` | O(c + k²) | O(k + m) | The raw read under `get_token()`, without pushback or source inclusion |
| Iterating a `shlex` | O(c + k²) per token | O(k + m) per token | One `get_token()` per step, with its bounds; stops at `eof` |
| `shlex.push_token(tok)` | O(1) | O(1) | `get_token()` returns the most recently pushed token first |
| `shlex.push_source(newstream, newfile=None)` | O(1); O(n) for a `str` | O(1); O(n) for a `str` | Stacks the current stream, file name and line number; reading continues from `newstream` |
| `shlex.pop_source()` | O(1) | O(1) | Closes the current stream and resumes the one below it; `get_token()` does this at the end of a pushed source |
| `shlex.sourcehook(newfile)` | O(1) | O(1) | Opens `newfile`, relative to the current file's directory; `get_token()` calls it with the token after the `source` keyword. The open itself is not priced here |
| `shlex.error_leader(infile=None, lineno=None)` | O(1) | O(1) | Formats `"file", line N: ` from the current file name and line |
| `shlex.commenters`, `shlex.wordchars`, `shlex.whitespace`, `shlex.whitespace_split`, `shlex.quotes`, `shlex.escape`, `shlex.escapedquotes`, `shlex.punctuation_chars` | O(1) | O(1) | Settings consulted per input character; changing them changes the tokens, not the bound. `punctuation_chars` is read-only after construction |
| `shlex.posix`, `shlex.eof`, `shlex.instream`, `shlex.infile`, `shlex.lineno`, `shlex.token`, `shlex.source`, `shlex.debug` | O(1) | O(1) | Lexer state; `eof` is `None` in POSIX mode and `''` otherwise |

## Splitting Command Lines

`split()` reads the whole string and returns every token, so it is linear while tokens stay short.
The per-token cost is what breaks that: the lexer extends the token it is building
one character at a time, and a k-character token costs O(k²), quoted or not.

```python
import shlex

tokens = shlex.split('git commit -m "Initial commit"')  # O(n + Σk²)
assert tokens == ['git', 'commit', '-m', 'Initial commit']

# str.split is O(n) at any token length, but it does not understand quotes
assert 'git commit -m "Initial commit"'.split()[3] == '"Initial'

# One long token is the worst case: O(k²) for its k characters
blob = 'x' * 1_000
assert shlex.split(f'--data {blob}') == ['--data', blob]
```

### Comments and Non-POSIX Mode

`comments=True` skips from `#` to the end of the line; `posix=False` keeps quotes in the tokens and
does not treat backslashes as escapes. Both change the tokens, not the cost.

```python
import shlex

line = 'key "some value"  # trailing comment'
assert shlex.split(line, comments=True) == ['key', 'some value']  # O(n + Σk²)
assert shlex.split(line) == ['key', 'some value', '#', 'trailing', 'comment']
assert shlex.split(r'a "b c" d\ e', posix=False) == ['a', '"b c"', 'd\\', 'e']
```

## Quoting Arguments

`quote()` is linear in the string. A non-empty string made only of shell-safe characters comes
back unchanged; anything else is wrapped in single quotes, with each embedded `'` spelled `'"'"'`.
`join()` quotes every argument, so `split(join(args))` gives the arguments back.

```python
import shlex

safe = 'file_name.txt'
assert shlex.quote(safe) is safe  # O(n) - returned as is
assert shlex.quote("it's here") == "'it'\"'\"'s here'"  # O(n)
assert shlex.quote('') == "''"

args = ['echo', 'Hello World', '$HOME', "it's"]
command = shlex.join(args)  # O(n + a)
assert command == "echo 'Hello World' '$HOME' 'it'\"'\"'s'"
assert shlex.split(command) == args
```

## Driving the Lexer Directly

### Reading Tokens One at a Time

A `shlex` object stops reading once it has a token, so taking the first few tokens of a large
stream costs what those calls read, not the stream. `push_token()` puts a token back for the next
`get_token()` to return.

```python
import io
import shlex

stream = io.StringIO('run --fast target\n' * 10_000)
lexer = shlex.shlex(stream, posix=True)  # O(1) - reads nothing yet
lexer.whitespace_split = True

assert lexer.get_token() == 'run'  # O(c + k²)
assert stream.tell() < 10  # only the first token has been read

lexer.push_token('again')  # O(1)
assert lexer.get_token() == 'again'  # O(1) - the pushed token comes first
assert lexer.get_token() == '--fast'
```

### Punctuation Characters

With `punctuation_chars`, runs of those characters become tokens of their own, which is how a
command line splits at `;`, `|` and `&&` without surrounding spaces.

```python
import shlex

lexer = shlex.shlex('ls -l|wc -l; echo done&&exit', posix=True, punctuation_chars=True)
tokens = list(lexer)  # O(n + Σk²)
assert tokens == ['ls', '-l', '|', 'wc', '-l', ';', 'echo', 'done', '&&', 'exit']
assert lexer.punctuation_chars == '();<>|&'
```

### Stacked Sources

`push_source()` switches input to another stream and remembers where it was; when that stream runs
out, `get_token()` pops back to the previous one. `error_leader()` names the current file and line
for an error message.

```python
import shlex

lexer = shlex.shlex('outer1 outer2', posix=True)
assert lexer.get_token() == 'outer1'

lexer.push_source('inner', 'included.txt')  # O(n) for a str source
assert lexer.get_token() == 'inner'
assert lexer.error_leader() == '"included.txt", line 1: '  # O(1)
assert lexer.get_token() == 'outer2'  # the pushed source ran out and was popped
assert lexer.infile is None
assert lexer.get_token() is None  # eof in POSIX mode
```

## Common Patterns

### Parsing a Config Line

```python
import shlex

def parse_config_line(line):
    tokens = shlex.split(line, comments=True)  # O(n + Σk²)
    if not tokens:
        return None, None
    return tokens[0], tokens[1] if len(tokens) > 1 else None

assert parse_config_line('url "postgresql://localhost/db"  # main') == (
    'url', 'postgresql://localhost/db'
)
assert parse_config_line('# only a comment') == (None, None)
```

## Performance Best Practices

✅ **Do**:

- Use `split()` for command lines and config lines, where tokens are short and the cost is linear
- Give `shlex()` an open stream for large input: a `str` is copied into a `StringIO` first
- Call `get_token()` or iterate the lexer when you need only the first few tokens; `split()` reads
  everything
- Build shell command strings with `join()` or `quote()` rather than by hand

❌ **Avoid**:

- Passing long unbroken values - encoded blobs, huge paths - through `split()` or `shlex()`: each
  token costs the square of its length
- `str.split()` on shell text - linear at any token length, but wrong for quoted arguments

## Version Notes

- **Python 3.12+**: `split(None)` raises `ValueError`; earlier versions emit a
  `DeprecationWarning` and read `sys.stdin`

## Related Modules

- **[subprocess](subprocess.md)** - takes the argument list `split()` produces, with no shell in
  between
- **[argparse](argparse.md)** - parses the argument list once it is split
- **[cmd](cmd.md)** - line-oriented command interpreters, whose handlers receive the unsplit
  argument string
