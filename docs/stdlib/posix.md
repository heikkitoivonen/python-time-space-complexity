# posix Module Complexity

The `posix` module is the C module beneath `os` on Unix, and exists only
there. Every public function it exposes is the same object `os` exposes under
the same name, so calling through `posix` saves nothing and costs nothing: the
bounds for `open()`, `read()`, `stat()`, `listdir()` and the rest are on the
[os page](os.md). The one name the two modules do not share is `environ`:
`posix.environ` is the plain `dict` the process environment was copied into
when the interpreter started, and `os.environ` is the mapping built over it.

Size variables: b = total bytes of the environment, keys and values together;
k = key length; v = value length.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `posix.open()`, `posix.read()`, `posix.stat()`, ... | as `os` | as `os` | The same function objects `os` exposes, not wrappers; see the [os page](os.md) for each bound |
| `posix.environ` (built at startup) | O(b) | O(b) | A plain `dict` of `bytes` keys and `bytes` values, copied from the C environment once |
| `posix.environ[key]` | O(k) | O(1) | A `dict` lookup; nothing is encoded or decoded, so every read returns the stored object |
| `posix.environ[key] = value` | O(k) | O(1) | Changes the `dict` only. `os.environ` reads it back, but the process environment does not change |
| `os.environ[key] = value` | O(k + v) | O(k + v) | Stores into this `dict` and calls `putenv()`, so both the `dict` and the process environment change |
| `os.putenv(key, value)` | O(k + v) | O(k + v) | Changes the process environment only, through the C library's `setenv()` and its scan; this `dict` is left as it was |
| `os.reload_environ()` | O(b) | O(b) | Rebuilds this `dict` in place from the process environment, 3.14+ |

## The functions are os's functions

`os` does not wrap `posix`; on Unix it imports the C module's functions into
its own namespace. There is no portability layer between the two to pay for,
and a bound established for `os.read()` is the bound of `posix.read()`.

```python
import os
import posix

assert posix.open is os.open  # the same function object, so the same cost
assert posix.read is os.read
assert posix.listdir is os.listdir

assert posix.environ is not os.environ  # the one name the two modules do not share
```

## posix.environ is the storage behind os.environ

`os.environ` is a mapping that encodes keys and values to `bytes` on the way
in and decodes them on the way out. On Unix the `dict` it stores into is
`posix.environ` itself, so a read through `posix.environ` returns the stored
`bytes` object, where the same read through `os.environ` decodes it again on
every read.

```python
import os
import posix

os.environ["GREETING"] = "hello there"  # O(k + v): encode, store here, then putenv()

assert posix.environ[b"GREETING"] == b"hello there"
assert posix.environ[b"GREETING"] is posix.environ[b"GREETING"]  # the stored object - O(1) space
assert os.environ["GREETING"] is not os.environ["GREETING"]  # decoded again on each read
```

## What reaches the process environment

Writing to the `dict` directly is a `dict` write and nothing more. `os.environ`
reads it back, because that is where it looks, but the process environment
handed to a child is not touched. `os.putenv()` is the mirror image: the
process environment changes and the `dict` does not. `os.environ` writes do
both, which is why it is the one to use.

```python
import os
import posix
import subprocess
import sys

posix.environ[b"DICT_ONLY"] = b"1"  # O(k): this dict, and nothing else
assert os.environ["DICT_ONLY"] == "1"  # os.environ reads from the same dict...
child = [sys.executable, "-c", "import os; print('DICT_ONLY' in os.environ)"]
assert subprocess.run(child, capture_output=True, text=True).stdout.strip() == "False"

os.putenv("PROCESS_ONLY", "1")  # the process environment, and nothing else
assert b"PROCESS_ONLY" not in posix.environ
```

## Related Modules

- [os Module](os.md) - the portable interface, and the bounds of every function here
- [posixpath Module](posixpath.md) - POSIX path operations
- [pathlib Module](pathlib.md) - object-oriented paths
