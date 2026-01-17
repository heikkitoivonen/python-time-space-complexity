# UUID Module Complexity

The `uuid` module provides utilities for creating and working with Universal Unique Identifiers (UUIDs).

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `uuid4()` | O(1) | O(1) | Generate random UUID |
| `uuid1()` | O(1) | O(1) | Generate time-based UUID |
| `UUID(string)` | O(n) | O(1) | Parse UUID from string |
| `UUID.hex` | O(1) | O(1) | Get hex representation |
| `UUID.bytes` | O(1) | O(1) | Get binary representation |

## UUID Generation

### uuid4() - Random UUID

#### Time Complexity: O(1)

```python
from uuid import uuid4

# Generate random UUID: O(1)
u = uuid4()  # O(1) - constant time random generation

# Use multiple times: O(k)
uuids = [uuid4() for _ in range(1000)]  # O(1000)

# UUID properties: O(1)
print(u.hex)      # Hex string
print(u.bytes)    # 16 bytes
print(u.int)      # 128-bit integer
print(u.version)  # 4
```

#### Space Complexity: O(1)

```python
from uuid import uuid4

u = uuid4()  # O(1) - 128-bit value
```

### uuid1() - Time-Based UUID

#### Time Complexity: O(1)

```python
from uuid import uuid1

# Generate time-based UUID: O(1)
u = uuid1()  # O(1) - current timestamp + mac address

# With specific node: O(1)
u = uuid1(node=12345678901)  # O(1)

# Properties: O(1)
print(u.time_low)  # Timestamp part
print(u.time_mid)
print(u.time_hi_version)
print(u.clock_seq)  # Clock sequence
print(u.node)       # MAC address or random
```

#### Space Complexity: O(1)

```python
from uuid import uuid1

u = uuid1()  # O(1) fixed size
```

## UUID Parsing and Conversion

### UUID Creation from String

#### Time Complexity: O(n)

Where n = length of string.

```python
from uuid import UUID

# Parse UUID: O(n) to parse string
u = UUID('12345678-1234-5678-1234-567812345678')  # O(36)

# Parse from hex: O(n)
u = UUID(hex='12345678123456781234567812345678')  # O(32)

# Parse from bytes: O(1) to create
u = UUID(bytes=b'\x00' * 16)  # O(1) - raw binary

# Parse from int: O(1)
u = UUID(int=123456789)  # O(1) - integer value
```

#### Space Complexity: O(1)

```python
from uuid import UUID

u = UUID('12345678-1234-5678-1234-567812345678')  # O(1)
```

## UUID Properties and Conversions

#### Time Complexity: O(1)

```python
from uuid import uuid4

u = uuid4()

# All representations are O(1)
print(u.hex)        # '12345678123456781234567812345678'
print(str(u))       # '12345678-1234-5678-1234-567812345678'
print(u.bytes)      # 16-byte string
print(u.bytes_le)   # Little-endian bytes
print(u.int)        # 340282366920938463463374607431768211456
print(u.fields)     # (time_low, time_mid, ...) tuple
print(u.version)    # UUID version (1-5)
print(u.variant)    # RFC 4122, reserved, etc.
```

#### Space Complexity: O(1)

```python
from uuid import uuid4

# All properties are computed on-the-fly
u = uuid4()
hex_str = u.hex  # O(1)
```

## Common Patterns

### Generate Unique IDs for Objects

```python
from uuid import uuid4

class User:
    def __init__(self, name):
        self.id = str(uuid4())  # O(1)
        self.name = name

users = [User(f'user_{i}') for i in range(1000)]  # O(1000)
```

### Create UUID Dictionary Key

```python
from uuid import uuid4

def track_object(obj):
    """Assign unique ID to object: O(1)"""
    return {
        'id': uuid4(),  # O(1)
        'data': obj
    }
```

### Batch UUID Generation

```python
from uuid import uuid4

def generate_batch(count):
    """Generate batch of UUIDs: O(n)"""
    return [uuid4() for _ in range(count)]  # O(n)

ids = generate_batch(10000)  # O(10000)
```

### Store UUID in Database

```python
from uuid import uuid4

def create_record(data):
    """Create record with UUID: O(1)"""
    record = {
        'id': uuid4().hex,  # O(1) - hex form for DB
        'data': data,
        'created_at': datetime.now()
    }
    return record
```

### UUID Validation

```python
from uuid import UUID

def is_valid_uuid(uuid_str):
    """Validate UUID format: O(n)"""
    try:
        UUID(uuid_str)  # O(n) to parse
        return True
    except ValueError:
        return False

# Usage
if is_valid_uuid(user_id):
    process(user_id)  # O(n) validation
```

## UUID Versions

### Version 1 - Time-Based

```python
from uuid import uuid1

# Time-based: current time + MAC address
u = uuid1()  # O(1)
print(f"Version: {u.version}")  # 1
print(f"Timestamp: {u.time}")   # Can extract time
```

### Version 4 - Random

```python
from uuid import uuid4

# Random: cryptographically secure random
u = uuid4()  # O(1)
print(f"Version: {u.version}")  # 4
# Best for most uses
```

### Version 3 & 5 - Namespace

```python
from uuid import uuid3, uuid5, NAMESPACE_DNS

# Deterministic from namespace + name
u3 = uuid3(NAMESPACE_DNS, 'example.com')  # O(n) hash
u5 = uuid5(NAMESPACE_DNS, 'example.com')  # O(n) hash

# Same input = same UUID
u3_again = uuid3(NAMESPACE_DNS, 'example.com')
assert u3 == u3_again  # True
```

## Performance Characteristics

### Best Practices

```python
from uuid import uuid4

# Good: Cache generated UUIDs
uid = uuid4()  # O(1)
for i in range(1000):
    use(uid)  # Reuse

# Good: Batch generation
ids = [uuid4() for _ in range(1000)]  # O(1000)

# Avoid: Redundant generation
for i in range(1000):
    if uuid4() == uuid4():  # Almost never true!
        pass

# Good: UUID4 for most cases
u = uuid4()  # Random, no collisions, O(1)

# Avoid: UUID1 if privacy concerns
u = uuid1()  # Contains MAC address!
```

### Storage Optimization

```python
from uuid import uuid4

u = uuid4()

# Good: Store as hex (no dashes)
hex_id = u.hex  # 32 chars, faster indexing

# OK: Store as string with dashes
str_id = str(u)  # 36 chars

# Good: Store as binary
binary_id = u.bytes  # 16 bytes, smallest
```

## Comparison with Random

```python
from uuid import uuid4
import random
import string

# UUID4 (better)
u = uuid4()  # O(1) - cryptographically secure, globally unique

# Random string (worse)
uid = ''.join(random.choices(string.ascii_letters, k=36))  # O(n) - collision possible

# UUID is guaranteed unique across systems and time
```

## Version Notes

- **Python 3.x**: Full UUID support
- **Python 3.6+**: UUID object improvements

## Related Documentation

- [Random Module](random.md) - Random number generation
- [Hashlib Module](hashlib.md) - Hash functions
