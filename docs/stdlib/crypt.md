# crypt Module Complexity

The `crypt` module hashes Unix passwords through the C library's `crypt(3)`. One call is one
hash, and its cost is chosen by the salt: the method it names and, for SHA-crypt and bcrypt, the
rounds it carries. Slowness is the point - a hash that is cheap to compute is cheap to guess.

!!! warning "Removed in Python 3.13"
    Deprecated in Python 3.11 and removed in Python 3.13 (PEP 594). The page covers the module
    as it is on Python 3.10 to 3.12 on Unix, and its examples run only there; from 3.11,
    `import crypt` emits a `DeprecationWarning`. Which methods work is up to the C library:
    `crypt.methods` lists the ones this one supports, and the examples assume Linux, where
    libxcrypt provides all five.

`r` is the rounds a salt carries and `w` is the length of the word in bytes. The salt, and the
hash each method returns, are bounded in length, so neither is a size variable.

## Complexity Reference

### Functions and methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `crypt.crypt(word, salt=None)` | the salt's method, below | O(1) | A `METHOD_*` value or `None` is turned into a salt by `mksalt()` first; `None` means `methods[0]`. A string, such as a stored hash, goes to the C library as it is |
| `crypt.mksalt(method=None, *, rounds=None)` | O(1) | O(1) | Hashes nothing; `rounds` is written into the salt and rejected with `ValueError` for a method without it or a value out of range |
| `crypt.methods` | O(1) | O(1) | The methods this C library supports, strongest first; built at import |

### Cost by method

The cost of `crypt.crypt()` with a salt of each method.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `crypt.METHOD_SHA512`, `crypt.METHOD_SHA256` | O(r·w) | O(1) | Every round rehashes the word. r is 5,000 unless `mksalt(rounds=...)` sets 1,000 to 999,999,999 |
| `crypt.METHOD_BLOWFISH` | O(r) | O(1) | bcrypt: only the first 72 bytes of the word count. r is a power of two from 16 to 2³¹, 4,096 from `mksalt()` |
| `crypt.METHOD_MD5` | O(w) | O(1) | A fixed 1,000 rounds; `rounds` raises `ValueError` |
| `crypt.METHOD_CRYPT` | O(1) | O(1) | Traditional DES: only the first 8 bytes of the word count |

## Hashing Passwords

### Hashing and Verifying

To check a password, hash it again with the stored hash as the salt: it carries the method,
rounds and salt the original hash used.

```python
import crypt
import hmac

stored = crypt.crypt('correct horse')  # the strongest method, default rounds
assert stored.startswith(f'${crypt.methods[0].ident}$')

attempt = crypt.crypt('correct horse', stored)  # the stored method and rounds
assert hmac.compare_digest(attempt, stored)
assert not hmac.compare_digest(crypt.crypt('wrong horse', stored), stored)
```

### Choosing the Rounds

The rounds live in the salt, so raising them makes each new hash dearer without touching the
hashes already stored. SHA-crypt is linear in the rounds and in the word; bcrypt is linear in
its rounds alone.

```python
import crypt

salt = crypt.mksalt(crypt.METHOD_SHA512, rounds=20_000)  # O(1) - nothing is hashed
assert salt.startswith('$6$rounds=20000$')
hashed = crypt.crypt('secret', salt)  # O(r·w), r = 20,000
assert crypt.crypt('secret', hashed) == hashed

bcrypt_salt = crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=1 << 8)  # 2⁸ rounds
assert bcrypt_salt.startswith('$2b$08$')

try:
    crypt.mksalt(crypt.METHOD_MD5, rounds=10_000)
except ValueError as error:
    assert 'rounds' in str(error)
else:
    raise AssertionError('MD5 accepted a rounds argument')
```

### Truncating Methods

Two methods stop reading the word early, which caps their cost and weakens them: DES uses 8
bytes and bcrypt 72, so words that share that prefix hash alike.

```python
import crypt

des = crypt.mksalt(crypt.METHOD_CRYPT)
assert crypt.crypt('password', des) == crypt.crypt('password-and-more', des)

bcrypt = crypt.mksalt(crypt.METHOD_BLOWFISH, rounds=16)
prefix = 'x' * 72
assert crypt.crypt(prefix, bcrypt) == crypt.crypt(prefix + 'ignored', bcrypt)
```

### Failures

libxcrypt does not raise for a salt it cannot use, or for a word of 512 bytes or more: it
returns a short failure string beginning with `*`, which never matches a stored hash. Other C
libraries may raise `OSError` instead.

```python
import crypt

assert crypt.crypt('secret', '!!').startswith('*')
assert crypt.crypt('x' * 512, crypt.mksalt(crypt.METHOD_SHA512)).startswith('*')
```

## Performance Best Practices

✅ **Do**:

- Verify with the stored hash as the salt, so the rounds and method it was made with are reused
- Raise SHA-crypt or bcrypt rounds to make guessing dearer; the cost is linear in them
- Compare hashes with `hmac.compare_digest()`
- Prefer `hashlib.scrypt()` or `hashlib.pbkdf2_hmac()` for new code, which outlives this module

❌ **Avoid**:

- `METHOD_CRYPT` and `METHOD_MD5` - the cheapest to guess, and DES ignores all but 8 bytes
- Hard-coding a method that the C library may not support; `crypt.methods` says which do
- Treating a hash that starts with `*` as a result - it is a failure

## Version Notes

- **Python 3.11+**: `import crypt` emits `DeprecationWarning`
- **Python 3.13+**: The module is removed; `import crypt` raises `ModuleNotFoundError`

## Related Modules

- **[hashlib](hashlib.md)** - `scrypt()` and `pbkdf2_hmac()`, the standard library's
  password hashes once this module is gone
- **[hmac](hmac.md)** - `compare_digest()` for comparing a hash without an early exit
- **[spwd](spwd.md)** - Reading stored hashes from the shadow password database, removed in
  Python 3.13
