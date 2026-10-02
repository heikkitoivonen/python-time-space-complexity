# getpass Module Complexity

The `getpass` module reads a password from the terminal with echo turned off, and looks up the
current user's login name. A prompt reads one line: the module holds that line and nothing else,
and it restores the terminal settings before it returns.

`n` is the characters typed and `p` is the characters in the prompt. Every bound leaves out the
time spent waiting for the user. `getuser()` reads at most four environment variables before it
falls back to one lookup in the user database, whose cost the system's backend decides; a user
name and an environment variable are priced at O(1).

## Complexity Reference

### Reading a password

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getpass.getpass(prompt='Password: ', stream=None, *, echo_char=None)` | O(p + n) | O(n) | Echo is off while the line is read, and the terminal settings are restored even when reading raises; `EOFError` on end of input |
| `getpass.getpass(..., echo_char='*')` | O(p + n) | O(n) | Python 3.14+: `echo_char` is written for each character typed, and the module rather than the terminal handles backspace; ignored when `getpass()` falls back |
| `getpass.unix_getpass(prompt='Password: ', stream=None)` | O(p + n) | O(n) | What `getpass()` is on Unix: tries `/dev/tty` first, then standard input, and writes the prompt to the terminal or `sys.stderr` unless `stream` is given |
| `getpass.win_getpass(prompt='Password: ', stream=None)` | O(p + n) | O(n) | What `getpass()` is on Windows: reads console keys with `msvcrt.getwch()`, and falls back when `sys.stdin` has been replaced |
| `getpass.fallback_getpass(prompt='Password: ', stream=None)` | O(p + n) | O(n) | Used when echo cannot be turned off: issues `GetPassWarning` and reads one line from `sys.stdin` with echo left as it is |

### Current user

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `getpass.getuser()` | O(1) | O(1) | The first non-empty of `LOGNAME`, `USER`, `LNAME` and `USERNAME`; otherwise one user-database lookup by uid on Unix. Nothing is cached |
| `getpass.GetPassWarning` | O(1) | O(1) | A `UserWarning` subclass, issued when input may be echoed |

## Reading a Password

### Echo Is Off While Reading

`getpass()` turns echo off, reads one line, and puts the terminal back as it found it. The
example drives it on a pseudo-terminal in a child process, so it runs without anyone typing.

```python
import os
import subprocess
import sys
import termios

controller, terminal = os.openpty()
child = subprocess.Popen(
    [sys.executable, '-c', 'import getpass; print(getpass.getpass())'],
    stdin=terminal, stderr=terminal, stdout=subprocess.PIPE,
    start_new_session=True, text=True,  # no controlling terminal: getpass uses stdin
)

shown = b''
while b'Password: ' not in shown:
    shown += os.read(controller, 1024)  # the prompt appears once echo is off
os.write(controller, b's3cret\n')       # O(n) - one line

assert child.stdout.read() == 's3cret\n'
assert child.wait() == 0
assert b's3cret' not in os.read(controller, 1024)  # the keys were not echoed
assert termios.tcgetattr(terminal)[3] & termios.ECHO  # and echo is back on
os.close(terminal)
os.close(controller)
```

### Masking Characters

From Python 3.14, `echo_char` is written for each character typed, so the user can see their
typing. It must be a single printable ASCII character.

```python
import getpass
import sys

if sys.version_info >= (3, 14):
    try:
        getpass.getpass(echo_char='**')  # O(1) - validated before the terminal is opened
    except ValueError as error:
        assert 'single printable ASCII character' in str(error)
    else:
        raise AssertionError('a two-character echo_char was accepted')
```

### Without a Terminal

On Unix, `getpass()` reads from the controlling terminal whenever there is one, even if standard
input is redirected. Only when neither `/dev/tty` nor standard input is a terminal does it give up
on turning echo off: it issues `GetPassWarning`, writes a warning line, and reads the password from
standard input as `input()` would.

```python
import subprocess
import sys

result = subprocess.run(
    [sys.executable, '-c', 'import getpass; print(getpass.getpass())'],
    input='s3cret\n', capture_output=True, text=True,
    start_new_session=True,  # no controlling terminal, and stdin is a pipe
)

assert result.stdout == 's3cret\n'
assert 'GetPassWarning' in result.stderr
assert 'Password input may be echoed' in result.stderr
```

## Finding the Current User

`getuser()` reads the environment first, so it returns whatever `LOGNAME` (or the next variable
set) says, not necessarily who owns the process. Only when all four are unset or empty does it
consult the user database. It reads them again on every call.

```python
import getpass
import os

saved = {name: os.environ.pop(name, None) for name in ('LOGNAME', 'USER', 'LNAME', 'USERNAME')}
try:
    os.environ['USER'] = 'alice'
    assert getpass.getuser() == 'alice'  # O(1)

    os.environ['LOGNAME'] = 'bob'
    assert getpass.getuser() == 'bob'  # LOGNAME is read first, and nothing was cached
finally:
    for name, value in saved.items():
        os.environ.pop(name, None)
        if value is not None:
            os.environ[name] = value

assert issubclass(getpass.GetPassWarning, UserWarning)
```

## Common Patterns

### Login Prompt

```python
import getpass
import hashlib
import hmac

def check(password, salt, expected):
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100_000)
    return hmac.compare_digest(derived, expected)  # constant-time comparison

def login(salt, expected):
    user = getpass.getuser()  # O(1)
    password = getpass.getpass(f'Password for {user}: ')  # O(p + n)
    return check(password, salt, expected)

salt = b'per-user salt'
expected = hashlib.pbkdf2_hmac('sha256', b's3cret', salt, 100_000)
assert check('s3cret', salt, expected)
assert not check('guess', salt, expected)
```

## Performance Best Practices

✅ **Do**:

- Expect `getpass()` on Unix to read from the controlling terminal even when standard input is a
  pipe; piped input reaches it only where there is no terminal
- Treat `GetPassWarning` as a sign the password may have been echoed, and catch `EOFError` for
  closed input

❌ **Avoid**:

- Reading a password with `input()` - the same O(n) line, but echoed to the screen
- Relying on `getuser()` to identify the process owner - it trusts the environment first

## Version Notes

- **Python 3.14+**: Added the `echo_char` keyword argument
- **Python 3.13+**: `getuser()` raises `OSError` when no name is found; before, the
  `KeyError` or `ImportError` from the user database propagated

## Related Modules

- **[termios](termios.md)** - the terminal attributes `getpass()` switches off and restores
- **[pwd](pwd.md)** - the user database `getuser()` falls back to
- **[msvcrt](msvcrt.md)** - the console calls `getpass()` uses on Windows
- **[os](os.md)** - `os.environ`, which `getuser()` reads first
