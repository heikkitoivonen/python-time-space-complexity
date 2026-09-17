# secrets Module Complexity

The `secrets` module is one `random.SystemRandom` instance behind a handful of
module-level functions. Every draw is a call to `os.urandom()`: there is no
state to seed, nothing is cached between calls, and each function costs the
bytes it asks the operating system for plus the encoding it applies to them. A
token costs its length, an integer costs its width in bits, and a choice costs
one draw the size of a sequence length, which fits a machine word.

## Complexity Reference

Size variables: n = bytes requested; w = bits in an integer, the bound given
to `randbelow()` or the width asked of `randbits()`; m = bytes in the second
value given to `compare_digest()`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `token_bytes(n)` | O(n) | O(n) | One `os.urandom(n)` call. Without n, `DEFAULT_ENTROPY` bytes |
| `token_hex(n)` | O(n) | O(n) | The same bytes, written as 2n hex digits |
| `token_urlsafe(n)` | O(n) | O(n) | The same bytes, written as Base64 without padding: about 4n/3 characters |
| `randbits(w)` | O(w) | O(w) | One draw of ceil(w/8) bytes, trimmed to w bits |
| `randbelow(n)` | O(w) expected | O(w) | w = bits in n. Draws w bits and draws again while the result is n or more; two rounds expected at worst, when n is a power of two |
| `choice(seq)` | O(1) expected | O(1) | One `randbelow(len(seq))` and one index lookup, so O(1) only where the length and the lookup are |
| `SystemRandom()` | O(1) | O(1) | The generator behind every function here, with the full [`random`](random.md) API at the same costs. `seed()` does nothing and `getstate()` raises |
| `compare_digest(a, b)` | O(m) | O(1) | [`hmac.compare_digest()`](hmac.md): every byte of b is compared whether or not an earlier one differed, or the lengths |
| `DEFAULT_ENTROPY` | — | — | 32, the bytes a token function draws when called without a size |

## A token costs the bytes it draws

Each token function makes one `os.urandom()` call for exactly the bytes asked
for, then encodes them. The encoding is what sets the output length: hex
writes two characters per byte, URL-safe Base64 four per three. Length is the
only lever on cost, and it is linear, so token size is never a reason to reach
for the insecure `random` generator.

```python
import secrets

# Each call is one os.urandom() draw of n bytes - O(n)
token = secrets.token_bytes(32)
assert len(token) == 32

# Hex writes two characters per byte
hex_token = secrets.token_hex(16)
assert len(hex_token) == 32

# URL-safe Base64 writes four characters per three bytes, without padding
url_token = secrets.token_urlsafe(32)
assert len(url_token) == 43 and "=" not in url_token

# No size means DEFAULT_ENTROPY bytes, 32 today
assert len(secrets.token_bytes()) == secrets.DEFAULT_ENTROPY
```

## An integer costs its width

`randbelow(n)` draws as many bits as n has, then draws again whenever the
result is not below n. A power of two is the worst bound, since half of all
draws are rejected, but the expected number of rounds never exceeds two. The
cost that does grow is the width: a draw is one `os.urandom()` call of
ceil(w/8) bytes and one integer built from them, so a 4096-bit bound costs
512 bytes per round and a bound below 256 costs one.

```python
import secrets

# Random integer in [0, 100): one byte per round - O(w)
random_int = secrets.randbelow(100)
assert 0 <= random_int < 100

# Every bit of a wide bound is drawn - O(w); 2**4096 is 4097 bits, 513 bytes a round
key_candidate = secrets.randbelow(2**4096)
assert key_candidate.bit_length() <= 4096

# randbits(w) is one draw of ceil(w/8) bytes, with no rejection loop - O(w)
nonce = secrets.randbits(128)
assert nonce.bit_length() <= 128

# Inclusive range [a, b] - O(w) in the width of the wider endpoint
def randint(a, b):
    return a + secrets.randbelow(b - a + 1)

rolls = [randint(1, 6) for _ in range(3)]
assert all(1 <= roll <= 6 for roll in rolls)
```

## A choice costs one `randbelow()`

`choice(seq)` is `randbelow(len(seq))` followed by one index lookup. A length
fits a machine word, so each round of that draw is a bounded number of bytes
however long the sequence, and the lookup is O(1) for a list, a string or a
range of word-sized integers. A password of `length` characters is therefore
`length` such calls.

```python
import secrets
import string

# One draw and one lookup per character - O(length)
def generate_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))

pwd = generate_password(16)
assert len(pwd) == 16
```

A recipe that rejects passwords missing a character class pays O(length) per
attempt, and the attempts are geometric in how often a draw passes. At twelve
characters most first attempts pass; at three almost none do; below three none
can, since two characters cannot hold an upper, a lower and a digit, and the
loop would never end.

```python
import secrets
import string

def generate_secure_password(length=12):
    if length < 3:
        raise ValueError("three character classes need at least three characters")
    alphabet = string.ascii_letters + string.digits + string.punctuation
    while True:  # O(length) per attempt; attempts fall as length grows
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in password)
                and any(c.islower() for c in password)
                and any(c.isdigit() for c in password)):
            return password

pwd = generate_secure_password(12)
assert len(pwd) == 12
```

## Drawing several winners

Picking k distinct entries from a list needs k `randbelow()` calls, not a
shuffle of the whole list. Swapping each pick to the end and popping it keeps
every removal O(1), so the selection is O(k) expected and the list shrinks by
k.
`SystemRandom().sample()` does the same job without mutating the list, at the
cost on the [`random`](random.md) page.

```python
import secrets

def lottery_selection(participants, winners=5):
    # O(1) per selection: swap with the last element, then pop - O(k) in all
    selected = []
    for _ in range(min(winners, len(participants))):
        idx = secrets.randbelow(len(participants))
        participants[idx], participants[-1] = participants[-1], participants[idx]
        selected.append(participants.pop())
    return selected

participants = list(range(100))
lucky = lottery_selection(participants, 5)
assert len(lucky) == len(set(lucky)) == 5
assert len(participants) == 95

# The same draw without mutation, at random.sample()'s cost
pool = list(range(100))
winners = secrets.SystemRandom().sample(pool, 5)
assert len(set(winners)) == 5 and len(pool) == 100
```

## Comparing tokens

`compare_digest()` is `hmac.compare_digest()` re-exported. It walks every
byte of its second argument whether or not an earlier one differed, or the
lengths, so its cost is that length and not where the values diverge, which is
what keeps the comparison from leaking how much of a token an attacker has
guessed. `==` stops at the first difference and does leak it.

```python
import secrets

expected = secrets.token_hex(32)
presented = expected[:-1] + ("0" if expected[-1] != "0" else "1")

# Every byte is compared - O(m) in the length, not in the position of the difference
assert secrets.compare_digest(expected, expected)
assert not secrets.compare_digest(expected, presented)
```

## Related Modules

- [random Module](random.md) - The `SystemRandom` API and its costs
- [hmac Module](hmac.md) - `compare_digest()` and message authentication
- [hashlib Module](hashlib.md) - Secure hashing
- [os Module](os.md) - `os.urandom()`, the source of every draw
