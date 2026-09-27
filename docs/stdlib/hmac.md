# hmac Module Complexity

The `hmac` module computes keyed message authentication codes (RFC 2104) over the fixed-size hashes
in `hashlib`, and compares digests without an early exit. An `HMAC` object is an inner and an outer
hash state keyed once, so like a hash object it absorbs each byte once and holds nothing
proportional to the data it has seen.

Bytes are the unit throughout. `n` is the message bytes passed to one call, `m` is key bytes, `k`
is the digest size in bytes, `b` is the hash's block size, and `c` is the length of the second
argument to `compare_digest()`. Both `k` and `b` are fixed per algorithm, so a bound in them alone
is constant for a given hash.

## Complexity Reference

### Functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hmac.new(key, msg=None, digestmod)` | O(m + n) | O(b) | `digestmod` is required: a `hashlib` name such as `'sha256'` or a constructor such as `hashlib.sha256`. A key longer than `b` is hashed once; a shorter one is padded to `b`. `key` must be `bytes` or `bytearray` |
| `hmac.digest(key, msg, digest)` | O(m + n) | O(b) | The same result as `new(key, msg, digest).digest()` in one call |
| `hmac.compare_digest(a, b)` | O(c) | O(1) | Walks the whole second argument wherever the first difference lies, and still walks it when the lengths differ. Both arguments must be ASCII `str` or both bytes-like, or it raises `TypeError` |

### HMAC

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HMAC.update(msg)` | O(n) | O(1) | Repeated calls equal one call on the concatenation |
| `HMAC.digest()` | O(b) | O(k) | A snapshot: the state is copied and the copy finalized, so the object stays usable and the cost is independent of what was absorbed |
| `HMAC.hexdigest()` | O(b) | O(k) | The same snapshot rendered as 2k hex characters |
| `HMAC.copy()` | O(b) | O(b) | Copies the keyed state without rekeying; the two objects then diverge freely |
| `HMAC.digest_size`, `HMAC.block_size`, `HMAC.name` | O(1) | O(1) | `k`, `b`, and `'hmac-'` plus the hash's name |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hmac.digest_size` | O(1) | O(1) | Always `None`; read `digest_size` from the instance |
| `HMAC.blocksize` | O(1) | O(1) | 64, the block size assumed for a hash that reports none |
| `hmac.trans_5C`, `hmac.trans_36` | O(1) | O(1) | 256-byte translation tables for the outer and inner key pads |

## Creating an HMAC

Construction keys two hash states and absorbs `msg` if one is given, so its cost is the key plus
the message. `hmac.digest()` does the same work when only the result is wanted.

```python
import hashlib
import hmac

key = b'secret-key'
message = b'data to sign' * 1000

h = hmac.new(key, message, hashlib.sha256)  # O(m + n)
assert h.name == 'hmac-sha256'
assert h.digest_size == 32 and h.block_size == 64  # O(1)

# One-shot: the same bytes in one call
assert hmac.digest(key, message, 'sha256') == h.digest()  # O(m + n)

# digestmod has no default
try:
    hmac.new(key, message)
except TypeError as error:
    assert 'digestmod' in str(error)
else:
    raise AssertionError('an HMAC was built without a digestmod')
```

### Long Keys

A key longer than the hash's block size is replaced by its digest before anything else happens.
That costs one pass over the key at construction and nothing afterwards.

```python
import hashlib
import hmac

long_key = b'x' * 1000  # longer than SHA-256's 64-byte block

h = hmac.new(long_key, b'data', hashlib.sha256)  # O(m) once, to hash the key
hashed_key = hashlib.sha256(long_key).digest()
assert h.digest() == hmac.new(hashed_key, b'data', hashlib.sha256).digest()
```

## Streaming Updates

`update()` absorbs its bytes and keeps only the keyed state, so a file of any size costs its
length in time and one chunk in memory.

```python
import hashlib
import hmac
import io

stream = io.BytesIO(b'a' * 1_000_000)
h = hmac.new(b'secret', digestmod=hashlib.sha256)  # O(1)

while chunk := stream.read(65536):
    h.update(chunk)  # O(n) per chunk, O(1) extra memory

assert h.digest() == hmac.digest(b'secret', b'a' * 1_000_000, 'sha256')
```

## Digests and Copies

A digest is a snapshot: the object stays usable afterwards, and the cost does not grow with what
it has absorbed. A copy clones the keyed state, which is the cheap way to authenticate many
messages sharing a key and a prefix.

```python
import hashlib
import hmac

h = hmac.new(b'secret', b'header:', hashlib.sha256)

digest = h.digest()  # O(b), independent of the bytes absorbed
assert h.digest() == digest  # nothing was finalized in place
assert h.hexdigest() == digest.hex()  # 2k characters

first = h.copy()   # O(b) - no rekeying, no replay of 'header:'
second = h.copy()
first.update(b'one')
second.update(b'two')
assert first.digest() == hmac.digest(b'secret', b'header:one', 'sha256')
assert second.digest() == hmac.digest(b'secret', b'header:two', 'sha256')
assert h.digest() == digest  # the original is untouched
```

## Comparing Digests

`compare_digest()` has no early exit: it walks every byte of its second argument whether the
first difference is at the start or the end, so its time reveals the length of what it compares
but not where the inputs differ. `==` stops at the first difference.

```python
import hashlib
import hmac

expected = hmac.digest(b'secret', b'message', 'sha256')
received = bytes(32)

assert hmac.compare_digest(expected, expected)  # O(c)
assert not hmac.compare_digest(received, expected)  # O(c), wherever they differ
assert not hmac.compare_digest(expected[:16], expected)  # different lengths: False

# Hex strings work too, if both are ASCII str
assert hmac.compare_digest(expected.hex(), expected.hex())

try:
    hmac.compare_digest(expected.hex(), expected)
except TypeError:
    pass
else:
    raise AssertionError('a str was compared with bytes')
```

## Common Patterns

### Signing and Verifying a Message

```python
import hashlib
import hmac

def sign(key, message):
    return hmac.new(key, message, hashlib.sha256).hexdigest()  # O(m + n)

def verify(key, message, signature):
    return hmac.compare_digest(sign(key, message), signature)  # O(m + n + c)

key = b'secret-key'
signature = sign(key, b'transfer 100')
assert verify(key, b'transfer 100', signature)
assert not verify(key, b'transfer 900', signature)
```

### Signing Requests With a Shared Prefix

```python
import hashlib
import hmac

base = hmac.new(b'api-secret', b'POST\n/v1/orders\n', hashlib.sha256)

def sign_body(body):
    h = base.copy()  # O(b) instead of rekeying and re-absorbing the prefix
    h.update(body)   # O(n)
    return h.hexdigest()

signature = sign_body(b'{"qty": 1}')
expected = hmac.new(b'api-secret', b'POST\n/v1/orders\n{"qty": 1}', hashlib.sha256)
assert hmac.compare_digest(signature, expected.hexdigest())
```

### Expiring Tokens

```python
import hashlib
import hmac

def make_token(secret, user_id, issued_at):
    payload = f'{user_id}:{issued_at}'
    tag = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return f'{payload}:{tag}'

def check_token(secret, token, now, max_age=3600):
    payload, _, tag = token.rpartition(':')
    expected = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(tag, expected):  # O(c)
        return None
    user_id, issued_at = payload.split(':')
    if now - int(issued_at) > max_age:
        return None
    return user_id

token = make_token(b'secret', 'alice', issued_at=1_000)
assert check_token(b'secret', token, now=1_500) == 'alice'
assert check_token(b'secret', token, now=10_000) is None  # expired
assert check_token(b'other', token, now=1_500) is None  # wrong key
```

## Performance Best Practices

✅ **Do**:

- Verify with `compare_digest()`, which takes the same time wherever the inputs differ
- Stream large inputs through `update()`; memory stays at the keyed state
- `copy()` a keyed object to authenticate many messages under one key or prefix

❌ **Avoid**:

- `==` on digests: it returns at the first differing byte, which leaks where they differ
- Reading a whole file into memory to pass as `msg`, when chunks through `update()` cost the same time
- Rebuilding an `HMAC` per message with a long key, when a copy skips hashing the key again

## Version Notes

- **Python 3.8+**: `digestmod` is required; `hmac.new(key, msg)` raises `TypeError`

## Related Modules

- **[hashlib](hashlib.md)** - the hash functions an HMAC is built on, and `pbkdf2_hmac()`
- **[secrets](secrets.md)** - random keys and tokens; `secrets.compare_digest` is this module's function
- **[base64](base64.md)** - encoding a digest for transport
