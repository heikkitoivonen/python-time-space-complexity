# netrc Module Complexity

The `netrc` module parses a `.netrc` file, the Unix format that stores login credentials per
host, into a dictionary. Constructing a `netrc` object reads and parses the whole file, a second
time in the locale encoding if it is not valid UTF-8; every lookup afterwards is a dictionary lookup that never touches the file again.

`n` is the characters in the file, `t` is the characters in its longest token (a host name,
login or password), and `r` is the characters in the text `repr()` rebuilds. Host-name hashing is
treated as O(1). The parsed entries and macros are the result, so parsing holds O(n) for as long
as the object lives.

## Complexity Reference

### netrc

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `netrc.netrc(file)` | O(n) | O(n) | One pass over the file; long tokens, many comments and many entries all stay linear. Python 3.10: O(n·t), since each character copies the token read so far |
| `netrc.netrc()` | O(n) | O(n) | Parses `~/.netrc`, with the same bound as a path; on POSIX it also checks the file's owner and mode. A missing file raises `FileNotFoundError` |
| `netrc.authenticators(host)` | O(1) | O(1) | Dict lookup that falls back to the `default` entry, then to `None`; returns the stored `(login, account, password)` tuple |
| `netrc.hosts` | O(1) | O(1) | The parsed dict of host name to `(login, account, password)`; a host listed twice keeps its last entry |
| `netrc.macros` | O(1) | O(1) | The parsed dict of macro name to its list of lines |
| `repr(netrc)` | O(r) | O(r) | Rebuilds `.netrc` text from `hosts` and `macros`; tokens are written unquoted, so one containing whitespace does not survive a round trip |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `netrc.NetrcParseError` | O(1) | O(1) | Raised for a syntax error and for a rejected `~/.netrc`; parsing stops at the first one |
| `NetrcParseError.msg`, `NetrcParseError.filename`, `NetrcParseError.lineno` | O(1) | O(1) | The message, and the file and line of a syntax error |

## Parsing a File

Construction is the whole cost: the file is read and parsed once, and nothing is read lazily
afterwards. Pass a path to parse a file other than `~/.netrc`.

```python
import netrc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'credentials')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(
            'machine example.com login alice password s3cret\n'
            'machine ftp.example.org login bob account acct password hunter2\n'
            'default login anonymous password guest\n'
        )

    rc = netrc.netrc(path)  # O(n) - reads and parses the whole file

login, account, password = rc.authenticators('example.com')  # O(1)
assert (login, password) == ('alice', 's3cret')
assert rc.authenticators('ftp.example.org') == ('bob', 'acct', 'hunter2')
assert rc.authenticators('unknown.example')[0] == 'anonymous'  # falls back to default
assert sorted(rc.hosts) == ['default', 'example.com', 'ftp.example.org']  # O(1) to reach
```

Without a `default` entry, an unknown host returns `None`. A syntax error raises
`NetrcParseError`, which carries the file and line.

```python
import netrc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'credentials')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('machine example.com login alice password s3cret\n')
    rc = netrc.netrc(path)  # O(n)
    assert rc.authenticators('unknown.example') is None  # O(1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write('machine example.com login alice\nhost other.example\n')
    try:
        netrc.netrc(path)
    except netrc.NetrcParseError as error:
        assert error.filename == path
        assert error.lineno == 2
        assert 'bad' in error.msg
    else:
        raise AssertionError('a bad token was parsed')
```

### Macros

A `macdef` block is kept verbatim, line by line, up to the blank line that ends it.

```python
import netrc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'credentials')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('macdef init\ncd /pub\nbinary\n\nmachine example.com login alice password s3cret\n')
    rc = netrc.netrc(path)  # O(n)

assert rc.macros == {'init': ['cd /pub\n', 'binary\n']}  # O(1) to reach
```

### The ~/.netrc Permission Check

Only `netrc()` with no argument checks the file. On POSIX it rejects a `~/.netrc` that another
user owns or that grants any permission to group or others; the same file passed by path is
parsed without the check. The example is for POSIX, where `HOME` decides what `~` means.

```python
import netrc
import os
import tempfile

saved_home = os.environ.get('HOME')
with tempfile.TemporaryDirectory() as home:
    path = os.path.join(home, '.netrc')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('machine example.com login alice password s3cret\n')
    os.chmod(path, 0o644)

    assert netrc.netrc(path).authenticators('example.com')  # by path: no check

    os.environ['HOME'] = home  # so that netrc() reads this file, not yours
    try:
        netrc.netrc()  # O(n) - ~/.netrc, with the owner and permission check
    except netrc.NetrcParseError as error:
        assert 'too permissive' in str(error)
    else:
        raise AssertionError('a group-readable ~/.netrc was accepted')
    finally:
        if saved_home is None:
            del os.environ['HOME']
        else:
            os.environ['HOME'] = saved_home
```

### Quoting and Comments

From Python 3.11, a token may be double-quoted or backslash-escaped, so a password can contain
spaces, and an entry without a `password` is accepted with the missing fields as `''`. A `#`
comment is skipped to the end of its line when it follows a non-blank line; after a blank line,
only its first word is skipped, and the rest of the line is read as tokens.

```python
import netrc
import os
import sys
import tempfile

def parse(text):
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'credentials')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        return netrc.netrc(path)  # O(n)

rc = parse('machine example.com login alice password s3cret  # work account\n')
assert rc.authenticators('example.com')[2] == 's3cret'

if sys.version_info >= (3, 11):
    rc = parse('machine example.com login alice password "two words"\n')
    assert rc.authenticators('example.com') == ('alice', '', 'two words')

    assert parse('machine example.com login alice\n').hosts == {
        'example.com': ('alice', '', '')
    }

    assert parse('machine a login u password p\n\n#work\n').hosts == {'a': ('u', '', 'p')}
    try:
        parse('machine a login u password p\n\n# the work account\n')
    except netrc.NetrcParseError as error:
        assert 'bad follower token' in str(error)
    else:
        raise AssertionError('a comment after a blank line was skipped')
```

## Rebuilding the File Text

`repr()` builds `.netrc` text from what was parsed, so it costs the length of that text. Comments
are gone, and tokens are written without quotes.

```python
import netrc
import os
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'credentials')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# personal\nmachine example.com login alice password s3cret\n')
    rc = netrc.netrc(path)

text = repr(rc)  # O(r)
assert text == 'machine example.com\n\tlogin alice\n\tpassword s3cret\n'
```

## Common Patterns

### Parse Once, Look Up Many Times

```python
import netrc
import os
import tempfile
from urllib.parse import urlsplit

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'credentials')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('machine api.example.com login alice password s3cret\n')
    rc = netrc.netrc(path)  # O(n), once

urls = ['https://api.example.com/v1/a', 'https://api.example.com/v1/b', 'https://cdn.example.com/x']
found = {}
for url in urls:
    host = urlsplit(url).hostname
    found[host] = rc.authenticators(host)  # O(1) per URL

assert found['api.example.com'][0] == 'alice'
assert found['cdn.example.com'] is None
```

## Performance Best Practices

✅ **Do**:

- Build one `netrc` object and reuse it: construction is the O(n) parse, and lookups are O(1)
- Pass a path for any file other than `~/.netrc`; only `netrc()` with no argument applies the
  owner and permission check
- Catch `NetrcParseError` where the file is user-edited; parsing stops at the first error

❌ **Avoid**:

- Constructing `netrc()` per request - every construction re-reads the file
- Writing `repr()` back to disk when a token contains whitespace - it is written unquoted and will
  not parse back the same

## Version Notes

- **Python 3.11+**: Parsing is O(n) at any token length; on 3.10 a t-character token costs
  O(t²), so a file is O(n·t)
- **Python 3.11+**: Tokens can be double-quoted or backslash-escaped; an entry needs no
  `password`, and missing `account` and `password` fields are `''` (a missing `account` is `None`
  on 3.10); a `macdef` that reaches the end of the file without a blank line raises; the
  `~/.netrc` check is skipped for the login `anonymous`
- **Python 3.11+**: After a blank line, only the first word of a `#` comment is skipped; the rest
  of the line is parsed as tokens, which usually raises `NetrcParseError`

## Related Modules

- **[shlex](shlex.md)** - shell-style tokenizing for other configuration formats
- **[configparser](configparser.md)** - INI-style configuration files
- **[getpass](getpass.md)** - prompting for a password instead of storing one
