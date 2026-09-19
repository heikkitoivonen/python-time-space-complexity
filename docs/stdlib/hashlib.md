# hashlib Module Complexity

The `hashlib` module computes message digests: MD5, the SHA-1, SHA-2 and SHA-3 families, the
SHAKE extendable-output functions and BLAKE2, plus the PBKDF2 and scrypt key derivation
functions. Every hash object holds a fixed-size state, so the module holds nothing proportional to
the data it has seen: each byte is absorbed once and forgotten.

Bytes are the unit throughout. `n` is the bytes passed to one call, `k` is the digest size in
bytes, `b` is the algorithm's block size, `L` is the output length asked of a SHAKE, `m` is
password bytes, `s` is salt bytes, `i` is PBKDF2 iterations, `c` is the derived-key blocks
⌈dklen / k⌉, and `N`, `r` and `p` are scrypt's own cost parameters. Both `k` and `b` are fixed
per algorithm, so a bound in them alone is constant for a given hash.

## Complexity Reference

### Constructors

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hashlib.md5(data=b'')`, `hashlib.sha1(data=b'')`, `hashlib.sha224(data=b'')`, `hashlib.sha256(data=b'')`, `hashlib.sha384(data=b'')`, `hashlib.sha512(data=b'')` | O(n) | O(b) | The state is one block plus a few words; `data` is absorbed at once |
| `hashlib.sha3_224(data=b'')`, `hashlib.sha3_256(data=b'')`, `hashlib.sha3_384(data=b'')`, `hashlib.sha3_512(data=b'')` | O(n) | O(b) | Same shape; a wider state and a larger `b` |
| `hashlib.shake_128(data=b'')`, `hashlib.shake_256(data=b'')` | O(n) | O(b) | Output length is chosen at `digest()` time, not here |
| `hashlib.blake2b(data=b'', *, digest_size=64, key=b'', salt=b'', person=b'', ...)`, `hashlib.blake2s(data=b'', *, digest_size=32, key=b'', salt=b'', person=b'', ...)` | O(n) | O(b) | A key is padded to one block and absorbed first; `salt` and `person` set state words. Sizes past `MAX_KEY_SIZE`, `SALT_SIZE`, `PERSON_SIZE` or `MAX_DIGEST_SIZE` raise `ValueError` |
| `hashlib.new(name, data=b'', *, usedforsecurity=True)` | O(n) | O(b) | One name lookup on top of the named constructor; an unknown name raises `ValueError`. `usedforsecurity=False` marks the digest as not used for security, which a FIPS-restricted build may require before it constructs MD5 or SHA-1; it changes availability, not cost |
| `blake2b.MAX_DIGEST_SIZE`, `blake2b.MAX_KEY_SIZE`, `blake2b.SALT_SIZE`, `blake2b.PERSON_SIZE`, `blake2s.MAX_DIGEST_SIZE`, `blake2s.MAX_KEY_SIZE`, `blake2s.SALT_SIZE`, `blake2s.PERSON_SIZE` | O(1) | O(1) | Integer class attributes: 64, 64, 16, 16 for BLAKE2b and 32, 32, 8, 8 for BLAKE2s |

### hash

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash.update(data)` | O(n) | O(1) | Repeated calls equal one call on the concatenation. From 2048 bytes the call runs without the GIL, so threads hash large buffers in parallel |
| `hash.digest()` | O(k) | O(k) | A snapshot: the state is copied and the copy finalized, so the object stays usable and the cost is independent of what was hashed |
| `hash.hexdigest()` | O(k) | O(k) | The same snapshot rendered as 2k hex characters |
| `hash.copy()` | O(b) | O(b) | Copies the state; the two objects then diverge freely. The cheap way to hash many inputs sharing a prefix |
| `hash.name`, `hash.digest_size`, `hash.block_size` | O(1) | O(1) | `digest_size` is 0 for a SHAKE, whose length is chosen per call |

### shake

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shake.digest(length)` | O(L) | O(L) | Any length; squeezing is linear in the bytes asked for, and each call snapshots the state as `digest()` does |
| `shake.hexdigest(length)` | O(L) | O(L) | 2L hex characters |

### Key derivation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hashlib.pbkdf2_hmac(hash_name, password, salt, iterations, dklen=None)` | O(m + c·(s + i)) | O(m + s + dklen) | OpenSSL keeps a copy of the password and salt; the password is keyed once; each of the c output blocks absorbs the salt once and then iterates i times, so `dklen` one byte past a multiple of k costs a whole extra block. `iterations` and `dklen` below 1 raise `ValueError` |
| `hashlib.scrypt(password, *, salt, n, r, p, maxmem=0, dklen=64)` | O(r·p·(N + s + dklen) + m) | O(r·(N + p) + m + s + dklen) | Memory-hard by design: the working set is 128·r·N bytes. A one-iteration PBKDF2 pass turns the password and salt into a 128·r·p buffer, and another absorbs that buffer once per output block of `dklen`. `maxmem=0` means OpenSSL's default cap of 32 MiB, and a combination over the cap raises `ValueError` before the working set is allocated; `n` must be a power of two |

### Files and algorithm names

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hashlib.file_digest(fileobj, digest, /)` | O(n) | O(1) for a file; O(n) once for a `BytesIO` still sharing its `bytes` | Python 3.11+. Reads a binary file through one fixed buffer (256 KiB) from its current position; a `BytesIO` is hashed whole from its buffer, and one still sharing the `bytes` it was built from copies them on the first call |
| `hashlib.algorithms_guaranteed` | O(1) | O(1) | A set of the 14 names every build provides; membership is O(1) |
| `hashlib.algorithms_available` | O(1) | O(1) | A set built once at import; includes what the linked OpenSSL adds |

## Hashing Data

### One Shot vs Incremental

`update()` absorbs each byte once and keeps only a fixed state, so streaming a large input
through it in chunks costs the same total as one call and never holds the input.

```python
import hashlib

data = b"x" * 1_000_000

one_shot = hashlib.sha256(data).hexdigest()  # O(n)

streamed = hashlib.sha256()  # O(1)
for start in range(0, len(data), 65_536):
    streamed.update(data[start:start + 65_536])  # O(chunk) each, O(n) total
assert streamed.hexdigest() == one_shot

# Only bytes-like data is accepted
try:
    hashlib.sha256("text")
except TypeError as error:
    assert 'encoded' in str(error)
else:
    raise AssertionError('a str was hashed')
```

### Digests Are Snapshots

`digest()` copies the state and finalizes the copy, so it costs the digest size whatever was
hashed before it, and the object keeps accepting data afterwards.

```python
import hashlib

h = hashlib.sha256(b"hello")  # O(n)
first = h.digest()            # O(k) - the state is copied, not consumed
assert h.digest() == first    # the same snapshot again
assert len(first) == h.digest_size == 32
assert len(h.hexdigest()) == 2 * h.digest_size  # O(k)

h.update(b" world")           # O(n) - still usable
assert h.digest() == hashlib.sha256(b"hello world").digest()
assert (h.name, h.block_size) == ('sha256', 64)
```

### Sharing a Prefix

`copy()` duplicates a fixed-size state, so hashing many inputs that share a long prefix costs the
prefix once plus each suffix, rather than the prefix once per input.

```python
import hashlib

prefix = b"header" * 100_000
suffixes = [b"a", b"b", b"c"]

base = hashlib.sha256(prefix)  # O(prefix) once
digests = []
for suffix in suffixes:
    branch = base.copy()       # O(b) - independent of the prefix length
    branch.update(suffix)      # O(suffix)
    digests.append(branch.hexdigest())

assert digests == [hashlib.sha256(prefix + s).hexdigest() for s in suffixes]
assert base.hexdigest() == hashlib.sha256(prefix).hexdigest()  # the base is untouched
```

### Hashing in Threads

An `update()` of 2048 bytes or more releases the GIL for the duration of the call, so threads
hashing large buffers run in parallel. A hash fed only smaller updates holds it, so a loop of
small updates gains nothing from threads.

```python
import hashlib
from concurrent.futures import ThreadPoolExecutor

blobs = [bytes([index]) * 4_000_000 for index in range(4)]

with ThreadPoolExecutor(max_workers=4) as pool:
    digests = list(pool.map(lambda blob: hashlib.sha256(blob).hexdigest(), blobs))  # O(n) each

assert digests == [hashlib.sha256(blob).hexdigest() for blob in blobs]
assert len(set(digests)) == 4
```

## Hashing Files

`file_digest()` reads a binary file through one fixed buffer, so memory stays flat however large
the file is. It reads from the file's current position. A `BytesIO` takes a different path: its
whole buffer is hashed in one call, and a `BytesIO` that still shares the `bytes` it was built
from, because the caller kept a reference, copies them the first time its buffer is exposed.

```python
import hashlib
import io
import os
import tempfile

payload = os.urandom(300_000)

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, 'blob.bin')
    with open(path, 'wb') as f:
        f.write(payload)

    with open(path, 'rb') as f:
        digest = hashlib.file_digest(f, 'sha256')  # O(n) time, O(1) memory
    assert digest.hexdigest() == hashlib.sha256(payload).hexdigest()

    with open(path, 'rb') as f:
        f.seek(100)
        tail = hashlib.file_digest(f, hashlib.sha256)  # from the current position
    assert tail.digest() == hashlib.sha256(payload[100:]).digest()

# A BytesIO is hashed whole, whatever its position
buffer = io.BytesIO(payload)
buffer.seek(100)
assert hashlib.file_digest(buffer, 'sha256').digest() == hashlib.sha256(payload).digest()

# Text mode is rejected
try:
    hashlib.file_digest(io.StringIO('text'), 'sha256')
except ValueError as error:
    assert 'binary' in str(error)
else:
    raise AssertionError('a text stream was hashed')
```

## Variable-Length Output

A SHAKE has no fixed digest size: `digest(length)` squeezes as many bytes as asked, in time and
memory linear in that length, and a longer request extends a shorter one.

```python
import hashlib

xof = hashlib.shake_128(b"seed")  # O(n)
assert xof.digest_size == 0        # the length is chosen per call

short = xof.digest(16)       # O(L)
long = xof.digest(1_000)     # O(L)
assert long[:16] == short    # a prefix of the same stream
assert len(xof.hexdigest(1_000)) == 2_000
```

## BLAKE2 Parameters

BLAKE2 takes its key, salt and personalization at construction and folds them into the fixed
state, so a keyed hash costs one extra block and no more; the limits are class attributes.

```python
import hashlib

assert (hashlib.blake2b.MAX_KEY_SIZE, hashlib.blake2b.SALT_SIZE) == (64, 16)
assert (hashlib.blake2s.MAX_KEY_SIZE, hashlib.blake2s.SALT_SIZE) == (32, 8)

message = b"payload" * 1_000
plain = hashlib.blake2b(message).digest()  # O(n)
keyed = hashlib.blake2b(message, key=b"secret", person=b"app").digest()  # O(n + b)
assert keyed != plain

short = hashlib.blake2b(message, digest_size=16)  # any size from 1 to MAX_DIGEST_SIZE
assert len(short.digest()) == short.digest_size == 16

try:
    hashlib.blake2b(key=b"k" * 65)
except ValueError as error:
    assert 'key length' in str(error)
else:
    raise AssertionError('an oversized key was accepted')
```

## Key Derivation

### PBKDF2

`pbkdf2_hmac()` is deliberately slow: it runs the HMAC once per iteration for every output
block. The password is keyed once, so its length is paid once rather than per iteration; the
iteration count is the knob, and asking for a `dklen` past a multiple of the digest size costs a
whole extra block.

```python
import hashlib

password = b"correct horse battery staple"
salt = b"16 random bytes."

key = hashlib.pbkdf2_hmac('sha256', password, salt, 100_000)  # O(m + c·(s + i)), c = 1
assert len(key) == 32  # dklen defaults to the digest size

longer = hashlib.pbkdf2_hmac('sha256', password, salt, 100_000, dklen=48)  # c = 2: twice the work
assert longer[:32] == key  # block one is unchanged

try:
    hashlib.pbkdf2_hmac('sha256', password, salt, 0)
except ValueError as error:
    assert 'greater than 0' in str(error)
else:
    raise AssertionError('zero iterations was accepted')
```

### scrypt

`scrypt()` is memory-hard: `n` and `r` set a working set of 128·r·N bytes that every one of the
`p` lanes walks twice. A request over `maxmem` fails before the working set is allocated, so the
cap decides what `n` can be.

```python
import hashlib

password = b"correct horse battery staple"
salt = b"16 random bytes."

key = hashlib.scrypt(password, salt=salt, n=2**14, r=8, p=1)  # O(N·r·p) time, 16 MiB working set
assert len(key) == 64  # dklen defaults to 64

try:
    hashlib.scrypt(password, salt=salt, n=2**16, r=8, p=1)  # 64 MiB, over the 32 MiB default cap
except ValueError as error:
    assert 'memory limit' in str(error)
else:
    raise AssertionError('a 64 MiB request fit under the default cap')

# Raising the cap admits it
big = hashlib.scrypt(password, salt=salt, n=2**16, r=8, p=1, maxmem=2**27)
assert len(big) == 64 and big != key
```

## Common Patterns

### Checksumming a Directory

```python
import hashlib
import os
import tempfile

def checksum_tree(root):
    """One digest over every file - O(total bytes) hashing, plus walking and sorting the entries."""
    tree = hashlib.sha256()
    for folder, dirs, files in os.walk(root):
        dirs.sort()  # walk subfolders in a fixed order
        for name in sorted(files):
            path = os.path.join(folder, name)
            with open(path, 'rb') as f:
                tree.update(hashlib.file_digest(f, 'sha256').digest())  # O(file) each, O(k) absorbed
    return tree.hexdigest()

with tempfile.TemporaryDirectory() as root:
    for name, content in [('a.txt', b'alpha'), ('b.txt', b'beta')]:
        with open(os.path.join(root, name), 'wb') as f:
            f.write(content)
    first = checksum_tree(root)
    with open(os.path.join(root, 'b.txt'), 'wb') as f:
        f.write(b'BETA')
    assert checksum_tree(root) != first
```

### Deduplicating by Content

```python
import hashlib

blobs = [b"same" * 1_000, b"other" * 1_000, b"same" * 1_000]

seen = {}
for index, blob in enumerate(blobs):
    key = hashlib.sha256(blob).digest()  # O(n) per blob
    seen.setdefault(key, []).append(index)  # O(1) amortized

duplicates = [group for group in seen.values() if len(group) > 1]
assert duplicates == [[0, 2]]
```

## Performance Best Practices

✅ **Do**:

- Stream a large input through `update()` or `file_digest()`; the state is fixed-size, so memory does not follow the input
- `copy()` a hash object once the shared prefix is absorbed, and hash only the suffixes
- Hash large buffers from threads; an `update()` of 2048 bytes or more releases the GIL
- Choose `pbkdf2_hmac()` iterations and scrypt's `n` for the cost you want; a KDF that is fast is not doing its job
- Use `algorithms_guaranteed` when the code must run on every build, `algorithms_available` when it may not

❌ **Avoid**:

- Reading a whole file into memory just to hash it; `file_digest()` needs one buffer
- Calling `hashlib.new(name)` in a hot loop when the name is fixed; the named constructor skips the lookup
- Asking `pbkdf2_hmac()` for a `dklen` past a multiple of the digest size unless the bytes are needed; each started block costs a full iteration run
- Passing a `BytesIO` built from a large `bytes` object to `file_digest()` when the `bytes` is at hand; hashing the `bytes` directly avoids the copy

## Version Notes

- **Python 3.11+**: Added `file_digest()`
- **Python 3.12+**: `pbkdf2_hmac()` comes only from OpenSSL; a build without it has no `pbkdf2_hmac` at all

## Related Modules

- **[hmac](hmac.md)** - Keyed digests for authentication, built on these hash objects
- **[secrets](secrets.md)** - Random salts and tokens to feed a key derivation function
- **[binascii](binascii.md)** - `crc32()` when a checksum, not a cryptographic digest, is enough
