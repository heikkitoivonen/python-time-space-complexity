# readline Module Complexity

The `readline` module wraps the C line-editing library behind `input()` and the interactive
interpreter: an in-memory history list, history files, and a tab-completion hook. It is Unix-only,
and the library underneath is either GNU readline or libedit (editline). The two keep the history
in different structures, so the history rows below give a bound for each where they differ.

`h` is the entries in the in-memory history. `i` is the position of the entry an indexed call
addresses, counted from the oldest. `F` is the characters in the file read or written, `L` is the
characters in a string argument, `k` is `nelements`, and `m` is the matches a completer returns
for one word. Bounds count entries and matches, treating each line as O(1); characters appear
only where `F` or `L` does.

## Complexity Reference

### History list

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `readline.add_history(string)` | O(1) amortized | O(1) | Appends at the newest end |
| `readline.get_current_history_length()` | O(1) | O(1) | Entries held now, not the file limit |
| `readline.get_history_item(index)` | O(i) libedit, O(1) GNU | O(1) | One-based; `None` outside the history. libedit walks from the oldest entry |
| `readline.replace_history_item(pos, line)` | O(i) libedit, O(1) GNU | O(1) | Zero-based; `ValueError` outside the history |
| `readline.remove_history_item(pos)` | O(i) libedit, O(h − i) GNU | O(1) | Zero-based; GNU readline shifts the newer entries down |
| `readline.clear_history()` | O(h) | O(1) | Frees every entry. Only present if the library provides it |
| `readline.set_auto_history(enabled)` | O(1) | O(1) | Whether `input()` adds each line it reads |
| Reading a line with `input()` | O(h) libedit, O(1) GNU, plus the line | O(1) | Compares the line with the newest entry and skips it if they are equal |

### History files

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `readline.read_history_file(filename=None)` | O(F) | O(F) | Appends every entry in the file to the in-memory list; `OSError` if it is missing |
| `readline.write_history_file(filename=None)` | O(F) | O(F) | Rewrites the file from the whole history |
| `readline.append_history_file(nelements, filename=None)` | O(k), or O(F) with a length set | O(k), or O(F) with a length set | Appends the newest k entries; a non-negative `set_history_length()` makes it pass over the whole file to truncate it. Only present if the library provides it |
| `readline.set_history_length(length)` | O(1) | O(1) | Caps the entries the two writers leave in the file; the in-memory list is never truncated. Negative means no cap; see the libedit warning below |
| `readline.get_history_length()` | O(1) | O(1) | The file cap, `-1` by default |

### Completion

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `readline.set_completer(function=None)` | O(1) | O(1) | `None` removes it |
| `readline.get_completer()` | O(1) | O(1) | The function object that was set |
| Completing one word | O(m) completer calls | O(m) | Calls `function(text, state)` for state 0, 1, 2, ... until it returns `None`: m + 1 calls |
| `readline.get_begidx()`, `readline.get_endidx()` | O(1) | O(1) | Where the word being completed starts and ends in the line buffer |
| `readline.get_completion_type()` | O(1) | O(1) | Which key started the completion |
| `readline.set_completer_delims(string)`, `readline.get_completer_delims()` | O(L) | O(L) | The characters that end a word |
| `readline.set_completion_display_matches_hook(function=None)` | O(1) | O(1) | GNU readline calls it to list matches; libedit lists them itself |

### Configuration, hooks and the line buffer

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `readline.parse_and_bind(string)` | O(L) | O(L) | One init-file line; the syntax differs between the two libraries |
| `readline.read_init_file(filename=None)` | O(F) | O(F) | Runs every line of an init file; `OSError` if it is missing |
| `readline.set_startup_hook(function=None)`, `readline.set_pre_input_hook(function=None)` | O(1) | O(1) | GNU readline calls them once per line read; libedit does not call them. `set_pre_input_hook` is only present if the library provides it |
| `readline.get_line_buffer()` | O(b) | O(b) | b = characters in the line being edited |
| `readline.insert_text(string)` | O(b + L) | O(L) | Inserts at the cursor |
| `readline.redisplay()` | O(b) | O(1) | Redraws the line being edited |
| `readline.backend` | O(1) | O(1) | `'readline'` or `'editline'`; Python 3.13+ |

## The History List

The in-memory history is where the two libraries differ. Adding an entry and asking how many
there are cost the same on both. Getting or replacing an entry by position costs O(1) on GNU
readline, which indexes an array; removing one shifts the newer entries down. libedit walks to the entry from the oldest one, so the cost
grows with the entry's distance from the oldest end: cheap near it, O(h) at the newest entry.

```python
import readline

for line in ['first', 'second', 'third']:
    readline.add_history(line)  # O(1) amortized

assert readline.get_current_history_length() == 3  # O(1)
assert readline.get_history_item(1) == 'first'  # one-based; O(i) on libedit
assert readline.get_history_item(99) is None

readline.replace_history_item(1, 'SECOND')  # zero-based; O(i) on libedit
readline.remove_history_item(0)  # zero-based; O(i) on libedit, O(h) on GNU readline
assert [readline.get_history_item(n) for n in (1, 2)] == ['SECOND', 'third']

try:
    readline.remove_history_item(5)
except ValueError as error:
    assert 'No history item' in str(error)
else:
    raise AssertionError('a missing position was removed')

readline.clear_history()  # O(h)
assert readline.get_current_history_length() == 0
```

### Reading the Whole History

The API has no bulk read, so reading every entry means one `get_history_item()` call per entry.
On libedit that is O(h²): each lookup walks from the oldest entry. If a program reads its history
back repeatedly, it should keep its own list of the lines it adds.

```python
import readline

readline.clear_history()
for n in range(100):
    readline.add_history(f'command {n}')

# O(h) on GNU readline, O(h²) on libedit
history = [
    readline.get_history_item(n)
    for n in range(1, readline.get_current_history_length() + 1)
]
assert history[0] == 'command 0' and history[-1] == 'command 99'
```

## History Files

`write_history_file()` rewrites the file from the whole history. `append_history_file(k)` writes
only the newest k entries, which is what makes it the cheaper call at the end of a session. That
holds only while no history length is set. `set_history_length()` does not limit the in-memory
list: it limits the file, and each of the two writers enforces it by passing over the whole file
after writing. With a limit set, `append_history_file()` costs O(F) like the full write.

!!! warning "Truncated files on libedit"
    When libedit truncates a history file to the length limit, it drops the file's header line,
    and `read_history_file()` then raises `OSError` for that file. Under libedit, cap the history
    yourself before writing rather than relying on `set_history_length()`.

```python
import os
import readline
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'history')

    readline.clear_history()
    for n in range(5):
        readline.add_history(f'line {n}')
    readline.write_history_file(path)  # O(F)

    readline.clear_history()
    readline.read_history_file(path)  # O(F) - appends to what is held
    assert readline.get_current_history_length() == 5

    readline.add_history('line 5')
    readline.append_history_file(1, path)  # O(k) - no length is set

    # The limit applies to the file only
    readline.set_history_length(3)  # O(1)
    readline.write_history_file(path)  # O(F), then truncated to 3 entries
    assert readline.get_current_history_length() == 6
    readline.set_history_length(-1)

    try:
        readline.read_history_file(os.path.join(directory, 'missing'))
    except OSError:
        pass
    else:
        raise AssertionError('a missing history file was read')
```

## Tab Completion

A completer is called with the word being completed and a state counter. readline keeps asking
for state 0, 1, 2, ... until the completer returns `None`, so one completion is m + 1 calls. Work the completer repeats on every call is repeated m + 1 times:
build the match list when `state` is 0 and index into it afterwards.

The binding that turns Tab into completion is spelled differently for each library.
`readline.backend` names the library on Python 3.13+; `readline.__doc__` mentions libedit on
every supported version.

```python
import readline

WORDS = ['apple', 'apricot', 'banana']
matches = []

def completer(text, state):
    if state == 0:  # O(len(WORDS)) once per completion
        matches[:] = [word for word in WORDS if word.startswith(text)]
    return matches[state] if state < len(matches) else None  # O(1)

readline.set_completer(completer)  # O(1)
assert readline.get_completer() is completer

if 'libedit' in readline.__doc__:
    readline.parse_and_bind('bind ^I rl_complete')
else:
    readline.parse_and_bind('tab: complete')

# What readline does when Tab is pressed after "ap": m + 1 calls
results = []
state = 0
while (result := completer('ap', state)) is not None:
    results.append(result)
    state += 1
assert results == ['apple', 'apricot'] and state == 2

readline.set_completer_delims(' \t\n')  # O(L)
assert readline.get_completer_delims() == ' \t\n'
```

## Common Patterns

### Keeping History Across Sessions

Read the file once at start-up, note how many entries it held, and at exit append only what the
session added. Several sessions can then share one file: each reads it once at start-up, and
saving does not pass over it again, provided no history length is set.

```python
import os
import readline
import tempfile

def load(path):
    try:
        readline.read_history_file(path)  # O(F)
    except FileNotFoundError:
        open(path, 'wb').close()  # GNU readline appends only to an existing file
    return readline.get_current_history_length()  # O(1)

def save(path, start):
    new = readline.get_current_history_length() - start
    readline.append_history_file(new, path)  # O(new entries)

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'history')

    for session in ['first', 'second']:
        readline.clear_history()
        start = load(path)
        readline.add_history(f'{session} command')  # input() would do this
        save(path, start)

    readline.clear_history()
    load(path)
    assert readline.get_history_item(1) == 'first command'
    assert readline.get_history_item(2) == 'second command'
```

## Performance Best Practices

✅ **Do**:

- Append a session's new entries with `append_history_file()`: O(k) against a full rewrite's O(F)
- Build a completer's match list once, at state 0; it is called m + 1 times per completion
- Keep your own list if a program reads its history back often; on libedit each lookup is O(i)
- Check `readline.backend` (3.13+) or `readline.__doc__` before choosing a `parse_and_bind()` syntax

❌ **Avoid**:

- Expecting `set_history_length()` to bound memory: it caps the file, and makes every write and
  append pass over the whole of it
- Looping `get_history_item()` over a long history on libedit - that is O(h²)
- Calling `append_history_file()`, `clear_history()` or `set_pre_input_hook()` without checking
  `hasattr()` where the library may lack them

## Version Notes

- **Python 3.13+**: Added `readline.backend`
- **Python 3.12.9+, 3.13.2+**: `append_history_file()` raises `ValueError` for a negative
  `nelements`
- **All Python 3**: History files written by one library may not be readable by the other

## Related Modules

- **[rlcompleter](rlcompleter.md)** - a ready-made completer for Python names
- **[code](code.md)** - interactive interpreters that read their lines through `readline`
- **[cmd](cmd.md)** - line-oriented command shells that install a completer
- **[atexit](atexit.md)** - where to save history when the program ends
