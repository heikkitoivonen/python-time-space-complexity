# hmac Module Complexity

The `hmac` module provides HMAC (Hash-based Message Authentication Code) functionality for cryptographic message authentication.

## Functions & Methods

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hmac.new(key, msg, digestmod)` | O(n) | O(1) | Create HMAC, n = msg size |
| `HMAC.update(msg)` | O(n) | O(1) | Add data to digest, k = hash block size |
| `HMAC.digest()` | O(k) | O(k) | Get binary digest, k = hash output size |
| `HMAC.hexdigest()` | O(k) | O(k) | Get hex digest |
| `hmac.compare_digest(a, b)` | O(n) | O(1) | Timing-safe for equal-length inputs |

## Creating HMAC

### Time Complexity: O(n)

Where n = message size.

```python
import hmac
import hashlib

# Create HMAC: O(n)
key = b'secret_key'
message = b'data to sign' * 1000

# One-shot: O(n)
h = hmac.new(key, message, hashlib.sha256)  # O(n)

# With bytes: O(n) to process entire message
digest = h.digest()  # O(k) where k = output size
```

### Space Complexity: O(1)

```python
import hmac
import hashlib

# No buffering of the full message (beyond the input itself)
h = hmac.new(key, message, hashlib.sha256)  # O(1) extra space
```

## Streaming Updates

### Time Complexity: O(n)

Where n = total size of all messages added.

```python
import hmac
import hashlib

# Streaming: process data incrementally
h = hmac.new(b'secret', digestmod=hashlib.sha256)

# Each update: O(m) per message
messages = [b'part1', b'part2', b'part3']
for msg in messages:
    h.update(msg)  # O(m) per update

# Total: O(n) where n = sum of all message sizes
digest = h.digest()  # O(k) where k = output size
```

### Space Complexity: O(k)

Where k = hash block size (not dependent on total data).

```python
import hmac
import hashlib

# Memory efficient: only keeps internal state
h = hmac.new(b'secret', digestmod=hashlib.sha256)

# Process huge amounts of data with O(k) memory
with open('huge_file.bin', 'rb') as f:
    while True:
        chunk = f.read(4096)  # Read chunks
        if not chunk:
            break
        h.update(chunk)  # O(k) memory, not O(total_size)
```

## Getting Digest

### Time Complexity: O(k)

Where k = hash output size.

```python
import hmac
import hashlib

h = hmac.new(b'secret', b'data', hashlib.sha256)

# Binary digest: O(k)
digest = h.digest()  # O(k) for SHA256 = O(32)

# Hex digest: O(k)
hex_digest = h.hexdigest()  # O(k) to convert
```

### Space Complexity: O(k)

```python
import hmac
import hashlib

h = hmac.new(b'secret', b'data', hashlib.sha256)

# Creates output of fixed size
digest = h.digest()  # O(k) space, SHA256 = 32 bytes
hex_digest = h.hexdigest()  # O(2k) space (hex encoded)
```

## Different Hash Algorithms

### Time Complexity by Algorithm

```python
import hmac
import hashlib

message = b'data' * 1000

# MD5: Deprecated (cryptographically broken)
# O(n) time
h = hmac.new(b'key', message, hashlib.md5)  # O(n)
digest = h.digest()  # O(16) bytes

# SHA1: Deprecated (cryptographically broken)
# O(n) time
h = hmac.new(b'key', message, hashlib.sha1)  # O(n)
digest = h.digest()  # O(20) bytes

# SHA256: Common, secure choice
# O(n) time
h = hmac.new(b'key', message, hashlib.sha256)  # O(n)
digest = h.digest()  # O(32) bytes

# SHA512: Larger digest size; performance varies by platform
# O(n) time
h = hmac.new(b'key', message, hashlib.sha512)  # O(n)
digest = h.digest()  # O(64) bytes
```

## Copy Operations

### Time Complexity: O(k)

```python
import hmac
import hashlib

h1 = hmac.new(b'secret', b'data1', hashlib.sha256)
h2 = hmac.new(b'secret', b'data2', hashlib.sha256)

# Copy HMAC state: O(k)
h_copy = h1.copy()  # O(k) to copy internal state

# Use copy for parallel processing
h1.update(b'more_data')  # O(m)
h_copy.update(b'other_data')  # O(m)

# Get separate digests
digest1 = h1.digest()  # O(k)
digest2 = h_copy.digest()  # O(k)
```

### Space Complexity: O(k)

```python
import hmac
import hashlib

h1 = hmac.new(b'secret', b'data', hashlib.sha256)

# Creates copy of state
h_copy = h1.copy()  # O(k) space
```

## Constant-Time Comparison

### Time Complexity: O(n)

Where n = length of digest (always full comparison).

```python
import hmac

# CRITICAL: Always use compare_digest for authentication
# Prevents timing attacks

# Received HMAC
received_hmac = b'abc123...'  # 32 bytes for SHA256

# Computed HMAC
computed_hmac = b'abc123...'  # computed value

# Bad: Direct comparison (timing attack vulnerable)
if received_hmac == computed_hmac:  # ❌ INSECURE
    # Time depends on where difference is
    # Early difference is fast, late difference is slow
    pass

# Good: Constant-time comparison
if hmac.compare_digest(received_hmac, computed_hmac):  # ✓ SECURE
    # Timing-safe for equal-length inputs; time depends on length
    pass
```

### Space Complexity: O(1)

```python
import hmac

# Just compares, no extra memory
result = hmac.compare_digest(hash1, hash2)  # O(1) space
```

## Common Patterns

### Simple Message Authentication

```python
import hmac
import hashlib

def sign_message(key, message):
    """Sign a message with HMAC."""
    return hmac.new(key, message, hashlib.sha256).hexdigest()  # O(n)

def verify_message(key, message, signature):
    """Verify message signature (constant-time comparison)."""
    expected = sign_message(key, message)  # O(n)
    return hmac.compare_digest(signature, expected)  # O(k), timing-safe
```

### Streaming Large Files

```python
import hmac
import hashlib

def hmac_file(key, filename):
    """Compute HMAC of file."""
    h = hmac.new(key, digestmod=hashlib.sha256)
    
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(65536)  # 64KB chunks
            if not chunk:
                break
            h.update(chunk)  # O(k) memory
    
    return h.hexdigest()  # Total: O(n) time, O(k) memory
```

### Authentication Token Generation

```python
import hmac
import hashlib
import time

def generate_token(secret, user_id):
    """Generate authenticated token."""
    # Include timestamp for token expiration
    timestamp = str(int(time.time())).encode()
    user_data = f'{user_id}:{timestamp}'.encode()
    
    token = hmac.new(secret, user_data, hashlib.sha256)  # O(n)
    return f'{user_data.decode()}:{token.hexdigest()}'

def verify_token(secret, token, max_age_seconds=3600):
    """Verify and extract user from token."""
    parts = token.rsplit(':', 1)
    user_data, signature = parts[0].encode(), parts[1]
    
    # Verify HMAC (constant-time)
    expected_sig = hmac.new(secret, user_data, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):  # O(k)
        return None
    
    # Check timestamp
    user_id, timestamp = user_data.decode().split(':')
    age = int(time.time()) - int(timestamp)
    
    if age > max_age_seconds:
        return None
    
    return user_id
```

### API Request Signing

```python
import hmac
import hashlib
import json

def sign_request(secret, method, path, body):
    """Sign API request for authentication."""
    # Create canonical request
    request_str = f'{method}\n{path}\n{body}'
    
    # HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode(),
        request_str.encode(),
        hashlib.sha256
    ).hexdigest()  # O(n)
    
    return signature

def verify_request(secret, method, path, body, signature):
    """Verify API request signature."""
    expected_sig = sign_request(secret, method, path, body)  # O(n)
    
    # Constant-time comparison
    return hmac.compare_digest(signature, expected_sig)  # O(k), timing-safe
```

## Performance Characteristics

### Best Practices

```python
import hmac
import hashlib

# Good: Use SHA256 (secure and standard)
h = hmac.new(b'key', b'data', hashlib.sha256)  # Secure

# Avoid: MD5 or SHA1 (cryptographically broken)
h = hmac.new(b'key', b'data', hashlib.md5)  # ❌ Broken

# Good: Use compare_digest for verification
if hmac.compare_digest(received, computed):  # ✓ Safe
    pass

# Avoid: Direct comparison (timing attack)
if received == computed:  # ❌ Vulnerable
    pass

# Good: Stream large data
h = hmac.new(b'key', digestmod=hashlib.sha256)
for chunk in read_large_file():
    h.update(chunk)  # O(k) memory

# Avoid: Load entire file at once
h = hmac.new(b'key', large_data, hashlib.sha256)  # ❌ O(n) memory
```

### Algorithm Selection

```python
import hmac
import hashlib

# MD5: BROKEN - DO NOT USE
# Fast but cryptographically broken

# SHA1: DEPRECATED - AVOID
# Still used in legacy systems but not recommended

# SHA256: RECOMMENDED - USE THIS
# Good balance of security and performance
h = hmac.new(b'key', b'data', hashlib.sha256)

# SHA512: Larger digest size
# Performance varies by platform
h = hmac.new(b'key', b'data', hashlib.sha512)
```

## Key Sizes

### Recommended Key Sizes

```python
import hmac
import hashlib

# HMAC key size recommendations
# At least as long as hash output size

# SHA256: use 32+ byte keys
key_256 = b'x' * 32
h = hmac.new(key_256, b'data', hashlib.sha256)

# SHA512: use 64+ byte keys
key_512 = b'x' * 64
h = hmac.new(key_512, b'data', hashlib.sha512)

# Keys longer than hash block size are hashed
# (block size = 64 for SHA256, 128 for SHA512)
very_long_key = b'x' * 1000
h = hmac.new(very_long_key, b'data', hashlib.sha256)
# Long key is automatically hashed
```

## Version Notes

- **Python 3.x**: `hmac` module available, including `compare_digest()`

## Related Documentation

- [hashlib Module](hashlib.md) - Hash functions
- [secrets Module](secrets.md) - Secure random number generation
- [base64 Module](base64.md) - Base64 encoding
