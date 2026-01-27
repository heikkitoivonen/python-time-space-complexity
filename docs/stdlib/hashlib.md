# hashlib Module Complexity

The `hashlib` module provides cryptographic hash functions including MD5, SHA1, SHA256, and others for generating digests of data.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hashlib.sha256(data)` | O(n) | O(1) | n = data size |
| `hash.update(data)` | O(n) | O(1) | n = new data size |
| `hash.digest()` | O(1) | O(k) | k = digest size (fixed per algorithm) |
| `hash.hexdigest()` | O(k) | O(k) | k = digest size |

## Creating Hash Objects

### Basic Hashing

```python
import hashlib

# Create SHA256 hash - O(n)
data = b"hello world"
h = hashlib.sha256(data)  # O(len(data))

# Get digest - O(1) return, O(k) copy
digest = h.digest()  # O(32) for SHA256

# Get hex representation - O(k)
hex_digest = h.hexdigest()  # O(64)
```

### Different Hash Algorithms

```python
import hashlib

data = b"test"

# MD5 - O(n)
h1 = hashlib.md5(data)  # O(4) - deprecated

# SHA1 - O(n)
h2 = hashlib.sha1(data)  # O(4)

# SHA256 - O(n)
h3 = hashlib.sha256(data)  # O(4)

# SHA512 - O(n)
h4 = hashlib.sha512(data)  # O(4)
```

## Streaming Hash

### Updating Hash

```python
import hashlib

# Create hash - O(n1)
h = hashlib.sha256(b"hello")  # O(5)

# Update with more data - O(n2)
h.update(b" ")  # O(1)
h.update(b"world")  # O(5)

# Final digest - O(1)
result = h.hexdigest()  # Same as sha256(b"hello world")
```

### Processing Large Files

```python
import hashlib

def hash_file(filename):
    """Hash file contents - O(n) where n = file size"""
    h = hashlib.sha256()  # O(1)
    
    with open(filename, 'rb') as f:
        # Process chunks - O(n) total
        while True:
            chunk = f.read(8192)  # O(8192)
            if not chunk:
                break
            h.update(chunk)  # O(8192)
    
    return h.hexdigest()  # O(k)

# Usage - O(n) where n = file size
file_hash = hash_file('largefile.bin')
```

## Hash-based Algorithms

### Password Hashing (Not Recommended)

```python
import hashlib

# Simple hash (not secure!) - O(n)
password = "mypassword".encode()
h = hashlib.sha256(password)  # O(10)
hashed = h.hexdigest()  # O(64)

# Problem: fast to compute, vulnerable to brute force
# Use bcrypt, argon2, or scrypt instead
```

### File Integrity

```python
import hashlib

def verify_file_hash(filename, expected_hash):
    """Verify file hasn't changed - O(n)"""
    actual_hash = hashlib.sha256()  # O(1)
    
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(8192)  # O(8192)
            if not chunk:
                break
            actual_hash.update(chunk)  # O(8192)
    
    return actual_hash.hexdigest() == expected_hash  # O(k)

# Usage
is_valid = verify_file_hash('file.zip', 'abc123...')  # O(n)
```

### Key Derivation

```python
import hashlib

# Simple KDF (not secure, use PBKDF2 or argon2) - O(n)
password = b"mypassword"
salt = b"randomsalt"

# PBKDF2 would be: hashlib.pbkdf2_hmac('sha256', password, salt, iterations)
# This does n iterations of hashing - O(n*hash_size)

h = hashlib.sha256(password + salt)  # O(n + salt_len)
derived_key = h.digest()  # O(32)
```

## Secure Hash Selection

### Algorithm Comparison

```python
import hashlib

data = b"test data"

# Available algorithms - O(n)
for algo in ['md5', 'sha1', 'sha256', 'sha512']:
    h = hashlib.new(algo, data)  # O(len(data))
    print(f"{algo}: {h.hexdigest()}")

# For new code, use SHA256 or SHA512
# MD5 and SHA1 should be avoided
```

## Common Patterns

### Checksum Multiple Files

```python
import hashlib
import os

def hash_directory(dirpath):
    """Hash all files in directory - O(n) where n = total size"""
    h = hashlib.sha256()  # O(1)
    
    for filename in os.listdir(dirpath):  # O(m) files
        filepath = os.path.join(dirpath, filename)
        
        if os.path.isfile(filepath):
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)  # O(8192)
    
    return h.hexdigest()

# Usage - O(n)
dir_hash = hash_directory('/path/to/dir')
```

### Deduplication

```python
import hashlib

def find_duplicates(files_list):
    """Find duplicate files by hash - O(n)"""
    file_hashes = {}  # hash -> [files]
    
    for filepath in files_list:  # O(m) files
        h = hashlib.sha256()  # O(1)
        
        # Hash file - O(file_size)
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        
        hash_val = h.hexdigest()  # O(k)
        
        if hash_val not in file_hashes:
            file_hashes[hash_val] = []
        file_hashes[hash_val].append(filepath)
    
    # Return duplicates
    return {h: files for h, files in file_hashes.items() if len(files) > 1}

# Usage - O(n) where n = total file size
duplicates = find_duplicates(file_list)
```

### Content-Addressed Storage

```python
import hashlib
import os

class ContentStore:
    """Store files by hash - O(1) lookup"""
    def __init__(self, base_dir):
        self.base_dir = base_dir  # O(1)
    
    def add_file(self, filepath):
        """Add file to store - O(n)"""
        h = hashlib.sha256()  # O(1)
        
        # Hash file
        with open(filepath, 'rb') as f:
            content = f.read()  # O(n)
            h.update(content)
        
        file_hash = h.hexdigest()  # O(k)
        store_path = os.path.join(self.base_dir, file_hash)
        
        # Store by hash
        with open(store_path, 'wb') as f:
            f.write(content)  # O(n)
        
        return file_hash
    
    def get_file(self, file_hash):
        """Retrieve file - O(1)"""
        store_path = os.path.join(self.base_dir, file_hash)
        with open(store_path, 'rb') as f:
            return f.read()  # O(n)

# Usage
store = ContentStore('/store')
hash_val = store.add_file('myfile.txt')  # O(n)
content = store.get_file(hash_val)  # O(n)
```

## Performance Considerations

### Hash Speed Comparison

```python
import hashlib
import time

data = b"x" * (1024 * 1024)  # 1MB

# MD5 (fast, insecure)
start = time.time()
hashlib.md5(data).digest()  # O(1MB)
md5_time = time.time() - start

# SHA256 (secure)
start = time.time()
hashlib.sha256(data).digest()  # O(1MB)
sha256_time = time.time() - start

# SHA512 (secure; speed varies by platform)
start = time.time()
hashlib.sha512(data).digest()  # O(1MB)
sha512_time = time.time() - start

print(f"MD5: {md5_time}")
print(f"SHA256: {sha256_time}")
print(f"SHA512: {sha512_time}")
```

### Incremental Updates

```python
import hashlib

# Full buffer - O(n)
data = b"x" * (1024 * 1024)
h1 = hashlib.sha256(data)
digest1 = h1.hexdigest()

# Incremental - O(n) total
h2 = hashlib.sha256()
for i in range(0, len(data), 4096):
    h2.update(data[i:i+4096])  # O(4096)
digest2 = h2.hexdigest()

# Same result, but can process streaming data
assert digest1 == digest2
```

## Available Algorithms

```python
import hashlib

# Algorithms guaranteed available
guaranteed = {
    'md5',
    'sha1',
    'sha224',
    'sha256',
    'sha384',
    'sha512',
    'blake2b',
    'blake2s',
    'sha3_224',
    'sha3_256',
    'sha3_384',
    'sha3_512',
    'shake_128',
    'shake_256',
}

# Algorithms available on system
available = set(hashlib.algorithms_available)

# New secure algorithms
secure_algos = {'sha256', 'sha384', 'sha512'}

# Check what's available
for algo in secure_algos:
    if algo in available:
        print(f"{algo}: available")
```

## Version Notes

- **Python 2.x**: hashlib available, fewer algorithms
- **Python 3.x**: Full algorithm support, OpenSSL integration
- **All versions**: O(n) complexity for hashing n bytes

## Related Modules

- **[hmac](hmac.md)** - Keyed hash for authentication
- **[secrets](secrets.md)** - Secure random generation
- **cryptography** - Full crypto library (external)

## Best Practices

✅ **Do**:

- Use SHA256 or SHA512 for new code
- Use PBKDF2 or Argon2 for password hashing
- Process large files in chunks
- Use hashlib.pbkdf2_hmac for key derivation
- Verify file integrity with hashes

❌ **Avoid**:

- Using MD5 or SHA1 (cryptographically broken)
- Using simple hash + salt for passwords (use bcrypt/argon2)
- Assuming hash uniqueness (collisions possible)
- Hashing passwords with just hashlib (too fast, vulnerable)
- Relying on hash for security (use HMAC instead)
