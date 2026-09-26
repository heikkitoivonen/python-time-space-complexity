# uuid Module Complexity

The `uuid` module generates and parses 128-bit universally unique identifiers. A `UUID` object
stores one 128-bit integer and nothing else of size: every field, byte string and text form is
computed from that integer when you ask for it, so all of them are constant-time.

`n` is the characters in a string passed to `UUID()`, `m` is the bytes in a name passed to
`uuid3()` or `uuid5()` (after UTF-8 encoding, for a `str`), and `k` is the UUIDs the command line
prints. Every other input has a fixed size. Reading the system clock, the operating system's
random source and the platform's own UUID generator is priced O(1). The one cost the page does not bound is the first call to
`getnode()`, which may run an external program.

## Complexity Reference

### Generating UUIDs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uuid.uuid1(node=None, clock_seq=None)` | O(1) | O(1) | Timestamp, clock sequence and node; calls `getnode()` when it needs a node and none is given |
| `uuid.uuid3(namespace, name)` | O(m) | O(m) | MD5 of the namespace's bytes followed by the name; the same inputs always give the same UUID. A `bytes` name needs Python 3.12+ |
| `uuid.uuid4()` | O(1) | O(1) | 16 bytes from `os.urandom()` |
| `uuid.uuid5(namespace, name)` | O(m) | O(m) | As `uuid3()`, with SHA-1 |
| `uuid.uuid6(node=None, clock_seq=None)` | O(1) | O(1) | Python 3.14+; `uuid1()`'s fields with the timestamp's high bits first, so it sorts by time; calls `getnode()` when no `node` is given |
| `uuid.uuid7()` | O(1) | O(1) | Python 3.14+; Unix milliseconds, a counter and random bits; sorts in creation order within a process |
| `uuid.uuid8(a=None, b=None, c=None)` | O(1) | O(1) | Python 3.14+; caller-supplied bits. An omitted block comes from `random`, which is not cryptographically secure |
| `uuid.getnode()`, first call | Varies | Varies | May run a program such as `ip` or `ifconfig` to find a MAC address; falls back to a random 48-bit number with the multicast bit set |
| `uuid.getnode()`, later calls | O(1) | O(1) | Returns the value found by the first call |

### UUID

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uuid.UUID(hex)` | O(n) | O(n) | n = string length; braces, hyphens and a `urn:uuid:` prefix are optional |
| `uuid.UUID(bytes=b)`, `uuid.UUID(bytes_le=b)`, `uuid.UUID(fields=t)`, `uuid.UUID(int=i)` | O(1) | O(1) | Fixed-size input, range-checked; `version=` overwrites the version and variant bits |
| `UUID.int`, `int(uuid)` | O(1) | O(1) | The stored value; besides `is_safe` it is all a `UUID` holds |
| `UUID.bytes`, `UUID.bytes_le` | O(1) | O(1) | 16 bytes; `bytes_le` reverses the byte order of the first three fields |
| `UUID.hex`, `str(uuid)`, `UUID.urn` | O(1) | O(1) | 32, 36 and 45 characters |
| `UUID.fields`, `UUID.time_low`, `UUID.time_mid`, `UUID.time_hi_version`, `UUID.clock_seq_hi_variant`, `UUID.clock_seq_low`, `UUID.node` | O(1) | O(1) | Bit slices of `int`; `fields` is the six as a tuple |
| `UUID.time`, `UUID.clock_seq` | O(1) | O(1) | Meaningful for the time-based versions only; `time` is Unix milliseconds for version 7 (Python 3.14+) |
| `UUID.version`, `UUID.variant` | O(1) | O(1) | `version` is `None` unless the variant is `RFC_4122` |
| `UUID.is_safe` | O(1) | O(1) | A `SafeUUID`; of the generators, only `uuid1()` sets it to anything but `unknown`, when the platform's generator reports it |
| `==`, `<`, `hash(uuid)` | O(1) | O(1) | Compare and hash the integer, so UUIDs sort and serve as dictionary keys |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uuid.NAMESPACE_DNS`, `uuid.NAMESPACE_URL`, `uuid.NAMESPACE_OID`, `uuid.NAMESPACE_X500` | O(1) | O(1) | Prebuilt `UUID` objects for `uuid3()` and `uuid5()` |
| `uuid.NIL`, `uuid.MAX` | O(1) | O(1) | Python 3.14+; all 128 bits clear, and all set |
| `uuid.RESERVED_NCS`, `uuid.RFC_4122`, `uuid.RESERVED_MICROSOFT`, `uuid.RESERVED_FUTURE` | O(1) | O(1) | The strings `UUID.variant` returns |
| `uuid.SafeUUID`, `SafeUUID.safe`, `SafeUUID.unsafe`, `SafeUUID.unknown` | O(1) | O(1) | Enum members for `UUID.is_safe` |

### Command-line interface

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `python -m uuid [-u NAME] [-n NAMESPACE] [-N NAME] [-C NUM]` | O(k) | O(1) | Python 3.12+; prints one `uuid4()` by default. k = UUIDs printed, set by `-C` on 3.14+; `uuid3` and `uuid5` make it O(k·m) time and O(m) space |

## Generating UUIDs

`uuid4()` is the constant-time default. `uuid3()` and `uuid5()` hash the name, so they cost its
length and give the same UUID for the same inputs. `uuid1()` with a `node` never needs
`getnode()`.

```python
import uuid

random_id = uuid.uuid4()  # O(1) - 16 bytes from os.urandom()
assert random_id.version == 4
assert random_id.variant == uuid.RFC_4122

named = uuid.uuid5(uuid.NAMESPACE_DNS, 'python.org')  # O(m)
assert named == uuid.uuid5(uuid.NAMESPACE_DNS, 'python.org')
assert str(named) == '886313e1-3b8a-5372-9b90-0c9aee199e5d'
assert str(uuid.uuid3(uuid.NAMESPACE_DNS, 'python.org')) == '6fa459ea-ee8a-3ca4-894e-db77e160355e'

stamped = uuid.uuid1(node=0x0123456789AB, clock_seq=0)  # O(1)
assert stamped.version == 1
assert stamped.node == 0x0123456789AB
```

### The Node and getnode()

`getnode()` finds the host's hardware address once per process. The first call may start a
program and wait for it; every call after that returns the stored value.

```python
import uuid

node = uuid.getnode()  # the first call may run an external program
assert 0 <= node < 2**48
assert uuid.getnode() == node  # O(1) - the stored value
```

### Sort Order

UUIDs compare by their integer. `uuid7()` and `uuid6()` put the timestamp in the high bits, so
values made in one process sort in the order they were made. `uuid1()` puts the low 32 bits of its
timestamp first and does not sort by time; `uuid4()` is random.

```python
import sys
import time
import uuid

if sys.version_info >= (3, 14):
    ids = [uuid.uuid7() for _ in range(1000)]  # O(1) each
    assert ids == sorted(ids)  # creation order
    assert abs(ids[-1].time - time.time_ns() // 1_000_000) < 1000  # Unix milliseconds
```

## Parsing and Converting

Parsing a string is linear in its length. Every other constructor and every attribute works on the fixed
128 bits.

```python
import uuid

u = uuid.UUID('{12345678-1234-5678-1234-567812345678}')  # O(n)
assert u == uuid.UUID('urn:uuid:12345678-1234-5678-1234-567812345678')
assert u == uuid.UUID(int=0x12345678123456781234567812345678)  # O(1)
assert u == uuid.UUID(bytes=u.bytes) == uuid.UUID(bytes_le=u.bytes_le)  # O(1)

assert u.hex == '12345678123456781234567812345678'  # O(1)
assert str(u) == '12345678-1234-5678-1234-567812345678'
assert u.urn == 'urn:uuid:12345678-1234-5678-1234-567812345678'
assert u.fields == (0x12345678, 0x1234, 0x5678, 0x12, 0x34, 0x567812345678)

# Only RFC 4122 variant UUIDs have a version
assert u.variant == uuid.RESERVED_NCS
assert u.version is None

try:
    uuid.UUID('not-a-uuid')
except ValueError as error:
    assert 'badly formed' in str(error)
else:
    raise AssertionError('a malformed string was parsed')
```

## Common Patterns

### Stable IDs From Names

```python
import uuid

def stable_id(url):
    return uuid.uuid5(uuid.NAMESPACE_URL, url)  # O(m)

assert stable_id('https://example.com/a') == stable_id('https://example.com/a')
assert stable_id('https://example.com/a') != stable_id('https://example.com/b')
```

### UUIDs as Keys

```python
import uuid

ids = [uuid.uuid4() for _ in range(1000)]  # O(1) each
index = {u: position for position, u in enumerate(ids)}  # O(1) per key

assert index[uuid.UUID(ids[10].hex)] == 10  # equal UUIDs hash equal
assert len(ids[0].bytes) < len(ids[0].hex) < len(str(ids[0]))  # 16 < 32 < 36
```

## Performance Best Practices

✅ **Do**:

- Use `uuid4()` for opaque identifiers: O(1), from the operating system's random source
- Use `uuid7()` on Python 3.14+ for keys that should sort in creation order
- Store `UUID.bytes`, 16 bytes, rather than the 36-character string when storage size matters
- Keep `uuid3()` and `uuid5()` names short; both are linear in the name

❌ **Avoid**:

- A first call to `getnode()` on a latency-sensitive path; `uuid6()` without a `node` calls it,
  and so can `uuid1()`
- `uuid8()` with omitted blocks for anything that must be hard to guess
- Expecting `uuid1()` or `uuid4()` values to sort in creation order

## Version Notes

- **Python 3.12+**: `uuid3()` and `uuid5()` accept a `bytes` name; added the `python -m uuid`
  command line
- **Python 3.14+**: Added `uuid6()`, `uuid7()`, `uuid8()`, `NIL` and `MAX`; `UUID.time` is
  milliseconds for version 7; the command line gains `-C`/`--count`

## Related Modules

- **[secrets](secrets.md)** - random tokens of any length, when the ID need not be a UUID
- **[hashlib](hashlib.md)** - the MD5 and SHA-1 behind `uuid3()` and `uuid5()`
- **[os](os.md)** - `os.urandom()`, the source of `uuid4()`
- **[random](random.md)** - the generator `uuid8()` draws omitted blocks from
