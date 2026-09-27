# antigravity Module Complexity

The `antigravity` module is an Easter egg. Importing it runs one call, `webbrowser.open()` on
[xkcd 353](https://xkcd.com/353/), so the first import in a process costs whatever that call
costs and returns when it does. It also defines `geohash()`, the
[xkcd 426](https://xkcd.com/426/) geohashing algorithm.

`n` is the bytes in `datedow`. The first import's bound uses the
[webbrowser](webbrowser.md) page's variables: `b` is the browsers in the preference order and
`p` is the directories on `PATH`. Loading `webbrowser` and `hashlib`, and any browser process
`webbrowser.open()` starts, are not priced. The coordinates are ordinary degree values, so
formatting them is fixed-size.

## Complexity Reference

### Importing the module

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import antigravity`, first in a process | O(b + p) | O(b + p) | One `webbrowser.open('https://xkcd.com/353/')`, which runs browser discovery first unless something in the process already has. Its result is ignored, so finding no browser is not an error |
| `import antigravity`, again | O(1) | O(1) | Found in `sys.modules`; the body does not run again, so no second browser |

### geohash

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `antigravity.geohash(latitude, longitude, datedow)` | O(n) | O(1) | `datedow` is bytes-like, not `str`; prints the coordinates and returns `None` |

## Importing the Module

The import waits for `webbrowser.open()` to return, and what that takes depends on the browser
that call reaches: when it is a text-mode browser, the import is held until the user quits. Replacing `webbrowser.open`
before the first import is how to load the module without a browser.

```python
import sys
import webbrowser
from unittest import mock

# A stand-in reporting that no browser was found
with mock.patch.object(webbrowser, 'open', return_value=False) as opened:
    import antigravity  # one webbrowser.open() call; False is not an error
    import antigravity  # O(1) - found in sys.modules, the body does not run again

opened.assert_called_once_with('https://xkcd.com/353/')
assert sys.modules['antigravity'] is antigravity
```

## Geohashing

`geohash()` hashes `datedow` with MD5 and turns the two halves of the digest into decimal
fractions that replace the fractional parts of the latitude and longitude. The hash is its only
work that grows with the input. It prints the result instead of returning it.

```python
import contextlib
import io
import webbrowser
from unittest import mock

with mock.patch.object(webbrowser, 'open'):  # the import would otherwise open a browser
    from antigravity import geohash

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    result = geohash(37.421542, -122.085589, b'2005-05-26-10458.68')  # O(n)

assert result is None
assert buffer.getvalue() == '37.857713 -122.544543\n'
```

## Performance Best Practices

✅ **Do**:

- Replace `webbrowser.open`, or register a preferred controller that reports success, before
  importing the module in a test or script, so the import's one `webbrowser.open()` call starts
  nothing
- Capture `geohash()` with `contextlib.redirect_stdout`; it returns `None`

❌ **Avoid**:

- Importing it on a text console where the browser `webbrowser.open()` reaches is a text-mode
  one: the import waits until that browser exits

## Related Modules

- **[webbrowser](webbrowser.md)** - what the first import's `webbrowser.open()` call costs
- **[hashlib](hashlib.md)** - the MD5 that `geohash()` runs over `datedow`
- **[this](this.md)** - the other Easter egg that acts when imported
