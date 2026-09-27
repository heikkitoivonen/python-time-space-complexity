# webbrowser Module Complexity

The `webbrowser` module hands a URL to a browser. It keeps a registry of browser controllers and
a preference order over them, built once per process by looking for known browsers, and
`open()` tries the controllers in that order until one reports success.

`b` is the browsers in the preference order and `p` is the directories on `PATH`. The bounds
count controllers tried and `PATH` probes, and assume a `BROWSER` variable of a few entries. String work on the URL is linear in its length and
negligible beside starting a process, so it is not priced. What a call costs in wall time is
set by the process a controller starts and whether it waits for that process, which the
controller rows say.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Browser discovery | O(p) | O(b + p) | Once per process, on the first `open()`, `get()` or `register()`: on Unix, a `PATH` lookup for each known graphical browser and one `xdg-settings` run when `DISPLAY` or `WAYLAND_DISPLAY` is set, for each text-mode browser when `TERM` is set, and for each `BROWSER` entry. It does not run again, so a browser installed later is not added to the order and a later `BROWSER` is not read |
| `webbrowser.open(url, new=0, autoraise=True)` | O(b) | O(1) | Tries controllers in preference order and stops at the first success; returns `False` if none succeeds. Nothing is remembered between calls, so a failing controller is tried again every time |
| `webbrowser.open_new(url)` | O(b) | O(1) | `open(url, 1)`: a new window if possible |
| `webbrowser.open_new_tab(url)` | O(b) | O(1) | `open(url, 2)`: a new tab if possible, otherwise as `open_new()` |
| `webbrowser.get(using=None)` | O(1) | O(1) | A registered name, or the first in preference order when `using` is `None`; returns the registered instance itself. A name that is not registered is looked up on `PATH`, O(p) time and space, and raises `Error` unless it is found there and its file name is a registered browser's |
| `webbrowser.get(command_line)` | O(1) | O(1) | A string containing `%s` is a command line: builds a new controller on each call. It waits for the command to exit unless the last word is `&` |
| `webbrowser.register(name, constructor, instance=None, *, preferred=False)` | O(1) amortized, O(b) with `preferred` | O(1) | Appends to the preference order; `preferred=True` inserts at the front. Without an `instance`, `get()` calls `constructor` each time |
| `webbrowser.Error` | O(1) | O(1) | Raised by `get()` when no runnable browser is found |

### Browser controllers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `controller.open(url, new=0, autoraise=True)`, text-mode browser or a `get()` command line without `&` | O(1) | O(1) | Starts one process and blocks until it exits: for `lynx`, `w3m` or `links`, until the user quits the browser. The exit status is the result |
| `controller.open(url, ...)`, `get()` command line ending in `&`, or `xdg-open` | O(1) | O(1) | Starts one process and returns without waiting for it |
| `controller.open(url, ...)`, Firefox, Chrome, Chromium, Opera, Epiphany | O(1) | O(1) | Runs the browser's remote-open command first and waits up to 5 seconds for it; if that command fails, starts the browser directly without waiting. At most two processes |
| `controller.open(url, ...)` on Windows or macOS | O(1) | O(1) | Hands the URL to the operating system and does not wait for the user to finish with the browser |
| `controller.open_new(url)`, `controller.open_new_tab(url)` | O(1) | O(1) | `open(url, 1)` and `open(url, 2)` |
| `controller.name` | O(1) | O(1) | The browser's system-dependent name |

### Command-line interface

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m webbrowser [-n \| -t] url` | O(b) | O(1) | One `open()` call; `-n` asks for a new window, `-t` a new tab |

## Opening a URL

### The Preference Order

`open()` walks the preference order and asks each controller in turn, so it costs one attempt
per controller up to the first that succeeds. Registering a controller with `preferred=True`
puts it at the front, which is also how to make `open()` testable without starting anything.

```python
import webbrowser

class Recorder:
    """A controller that records the call instead of starting a browser."""

    def __init__(self, name, succeeds=True):
        self.name = name
        self.succeeds = succeeds
        self.calls = []

    def open(self, url, new=0, autoraise=True):
        self.calls.append((url, new))
        return self.succeeds

    def open_new(self, url):
        return self.open(url, 1)

    def open_new_tab(self, url):
        return self.open(url, 2)

url = 'https://www.example.com'
fallback = Recorder('fallback')
webbrowser.register('fallback', None, fallback, preferred=True)  # O(b) - front of the order

assert webbrowser.open(url) is True          # O(b) - stops at the first success
assert webbrowser.open_new(url) is True      # new=1
assert webbrowser.open_new_tab(url) is True  # new=2
assert fallback.calls == [(url, 0), (url, 1), (url, 2)]

# A controller that fails is tried, then the next one is asked
failing = Recorder('failing', succeeds=False)
webbrowser.register('failing', None, failing, preferred=True)  # now first

assert webbrowser.open(url) is True
assert webbrowser.open(url) is True
assert len(failing.calls) == 2  # tried again on every call
assert fallback.calls[-2:] == [(url, 0), (url, 0)]
```

### Discovery Runs Once

The first call that needs the registry builds it. On Unix that is a `PATH` lookup for each
browser the environment could use: graphical ones when a display is set, together with an
`xdg-settings` run to find the desktop's default, and text-mode ones when `TERM` is set. The
result lasts for the process, so later calls skip it and a `BROWSER` set afterwards is not seen.

```python
import os
import webbrowser

try:
    webbrowser.get('no-such-browser')  # discovery, then one O(p) PATH lookup
except webbrowser.Error as error:
    assert 'could not locate runnable browser' in str(error)
else:
    raise AssertionError('an unknown browser was found')

os.environ['BROWSER'] = 'no-such-browser'
try:
    webbrowser.get('no-such-browser')  # discovery does not run again
except webbrowser.Error:
    pass
else:
    raise AssertionError('BROWSER was read after discovery')
```

## Choosing a Controller

### Blocking and Background Controllers

`get()` with a command line builds a controller for it. Without a trailing `&`, `open()` waits
for the command to exit and reports its status; with one, it returns as soon as the process has
started. Text-mode browsers are the first kind, which is why `open()` on a terminal with no
graphical browser blocks until the user quits.

```python
import shlex
import sys
import webbrowser

url = 'https://www.example.com'

exits_3 = shlex.join([sys.executable, '-c', 'import sys; sys.exit(3)'])
blocking = webbrowser.get(exits_3 + ' %s')  # O(1) - a new controller
assert blocking.open(url) is False  # waited for the exit status

sleeps = shlex.join([sys.executable, '-c', 'import time; time.sleep(1)'])
background = webbrowser.get(sleeps + ' %s &')  # trailing '&' - does not wait
assert background.open(url) is True  # still running when open() returned
```

### Reusing a Registered Controller

A registered instance comes back from `get()` as itself, in O(1). Calling its `open()` directly
skips the walk over the preference order that `webbrowser.open()` repeats on every call.

```python
import webbrowser

class Recorder:
    name = 'recorder'

    def __init__(self):
        self.urls = []

    def open(self, url, new=0, autoraise=True):
        self.urls.append(url)
        return True

recorder = Recorder()
webbrowser.register('recorder', None, recorder)  # O(1) amortized - appended

browser = webbrowser.get('recorder')  # O(1) - the registered instance
assert browser is recorder
assert browser.name == 'recorder'

for page in ('a', 'b', 'c'):
    assert browser.open(f'https://www.example.com/{page}')  # O(1) each, no walk
assert len(recorder.urls) == 3
```

## Performance Best Practices

✅ **Do**:

- Call `get()` once and reuse the controller for many URLs; `webbrowser.open()` walks the
  preference order, failing controllers included, on every call
- End a `get()` command line with `&` when the caller must not wait for the browser
- Register a recording controller with `preferred=True` in tests, so `open()` starts nothing

❌ **Avoid**:

- `webbrowser.open()` from code that must not block, on a machine that may only have a
  text-mode browser: it waits until the user quits it
- Setting `BROWSER` or installing a browser after the first call and expecting the preference
  order to change; discovery has already run

## Related Modules

- **[subprocess](subprocess.md)** - what every Unix controller uses to start the browser
- **[shutil](shutil.md)** - `shutil.which()`, the O(p) `PATH` lookup behind discovery
- **[urllib](urllib.md)** - build and quote the URL before handing it over
