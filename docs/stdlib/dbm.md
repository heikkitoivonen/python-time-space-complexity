# dbm Module Complexity

The `dbm` module provides interfaces to various Unix database implementations, allowing persistent key-value storage with different backend options for different performance/compatibility needs.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dbm.open()` | O(1) | O(1) | Open/create database |
| `db[key] = value` | O(1) to O(log n) | O(k) | Backend-dependent; gdbm is O(1) avg |
| `db[key]` | O(1) to O(log n) | O(1) | Backend-dependent; gdbm is O(1) avg |
| `del db[key]` | O(1) to O(log n) | O(1) | Backend-dependent |
| `key in db` | O(1) to O(log n) | O(1) | Backend-dependent |
| `db.keys()` | O(n) | O(n) | Get all keys (slow) |
| `db.close()` | O(n) | O(1) | Flush and close |

## DBM Variants

### Available Backends

```python
import dbm

# Auto-detect appropriate backend
db = dbm.open('mydb')  # O(1)

# dbm.dumb - pure Python (slow, always available)
db = dbm.dumb.open('mydb')  # O(1)

# dbm.gnu - GNU DBM (fast, Linux/Unix)
try:
    db = dbm.gnu.open('mydb')  # O(1)
except ImportError:
    print("GNU DBM not available")

# dbm.ndbm - Berkeley DB (legacy)
try:
    db = dbm.ndbm.open('mydb')  # O(1)
except ImportError:
    print("NDBM not available")

# Detect which backend is available
import dbm
backend = dbm.whichdb('mydb')  # O(1) detect
print(f"Using: {backend}")
```

### Recommended Backends

```
Priority:
1. dbm.gnu - Fastest, most reliable (Linux/Unix)
2. dbm.ndbm - Berkeley DB (Unix systems)
3. dbm.dumb - Pure Python (slow but portable)

For new code: Use shelve + dbm.gnu
For portability: Use shelve + dbm.dumb
```

## Basic Key-Value Operations

### Store and Retrieve

```python
import dbm

# Open database - O(1)
db = dbm.open('mydata', 'c')

# Store key-value pairs - O(log n) each
db[b'name'] = b'Alice'      # Must use bytes!
db[b'age'] = b'30'
db[b'score'] = b'95.5'

# Retrieve values - O(log n)
name = db[b'name']         # b'Alice'
age = db[b'age']           # b'30'

# Check key existence - O(log n)
if b'name' in db:
    print(f"Name: {db[b'name']}")

# Close database - O(n) flush
db.close()
```

### String Encoding

```python
import dbm

db = dbm.open('strings', 'c')

# DBM requires bytes, so encode/decode
key = 'username'
value = 'john_doe'

# Store - encode to bytes - O(log n)
db[key.encode()] = value.encode()

# Retrieve - decode from bytes - O(log n)
retrieved = db[key.encode()].decode()
print(retrieved)  # 'john_doe'

db.close()
```

## Iteration and Keys

### Iterate Keys

```python
import dbm

db = dbm.open('data', 'c')

# Store multiple items - O(log n) each
db[b'user1'] = b'Alice'
db[b'user2'] = b'Bob'
db[b'user3'] = b'Charlie'

# Get all keys - O(n) expensive!
keys = db.keys()
for key in keys:
    print(f"{key}: {db[key]}")

# Direct iteration - O(n)
for key in db:
    print(f"{key}: {db[key]}")

# Check count
print(len(db))  # May not be O(1)

db.close()
```

## Modifications

### Update and Delete

```python
import dbm

db = dbm.open('data', 'c')

# Store initial value - O(log n)
db[b'counter'] = b'0'

# Update - O(log n)
db[b'counter'] = b'1'
db[b'counter'] = b'2'

# Delete key - O(log n)
db[b'temp'] = b'data'
del db[b'temp']

# Conditional delete
if b'temp' in db:
    del db[b'temp']

db.close()
```

## Context Manager

### Automatic Cleanup

```python
import dbm

# Use context manager - O(1) open
with dbm.open('data', 'c') as db:
    
    # Store - O(log n)
    db[b'key'] = b'value'
    
    # Retrieve - O(log n)
    value = db[b'key']
    print(value)

# Automatically closed
```

## File Modes

### Open Modes

```python
import dbm

# 'r' - read-only - O(1)
db = dbm.open('data', 'r')
value = db[b'key']

# 'w' - read-write, fails if not exists - O(1)
try:
    db = dbm.open('newdata', 'w')
except Exception as e:
    print("Database doesn't exist")

# 'c' - read-write, create if missing (default) - O(1)
db = dbm.open('data', 'c')

# 'n' - always create new, truncate if exists - O(1)
db = dbm.open('data', 'n')

db.close()
```

## Data Type Restrictions

### Keys and Values Must Be Bytes

```python
import dbm

db = dbm.open('data', 'c')

# Correct: use bytes
db[b'key'] = b'value'
db[b'number'] = b'42'
db[b'list'] = b'[1, 2, 3]'

# Wrong: strings, integers, objects won't work
try:
    db['key'] = 'value'  # TypeError
except TypeError as e:
    print(f"Error: {e}")

# Wrong: mutable objects
try:
    db[b'list'] = [1, 2, 3]  # TypeError
except TypeError as e:
    print(f"Error: {e}")

# Workaround: convert to/from strings
import json
data = {'name': 'Alice', 'age': 30}
db[b'user'] = json.dumps(data).encode()
retrieved = json.loads(db[b'user'].decode())

db.close()
```

## Performance Characteristics

### Backend Comparison

```python
import dbm
import dbm.dumb
import time

data = [(f'key{i}'.encode(), f'value{i}'.encode()) for i in range(1000)]

# dbm.dumb (slowest but portable)
start = time.time()
with dbm.dumb.open('dumb_test', 'n') as db:
    for key, value in data:
        db[key] = value
dumb_time = time.time() - start

# dbm.gnu (fast, if available)
try:
    import dbm.gnu
    start = time.time()
    with dbm.gnu.open('gnu_test', 'n') as db:
        for key, value in data:
            db[key] = value
    gnu_time = time.time() - start
    print(f"GNU: {gnu_time:.4f}s vs Dumb: {dumb_time:.4f}s")
except ImportError:
    print("GNU DBM not available")
```

## Common Patterns

### Simple Cache

```python
import dbm
import json
import time

class PersistentCache:
    """Simple DBM-based cache"""
    
    def __init__(self, path='cache.db'):
        self.db = dbm.open(path, 'c')
    
    # Set with TTL
    def set(self, key, value, ttl=None):
        """Store with optional expiration - O(log n)"""
        entry = {
            'value': value,
            'time': time.time(),
            'ttl': ttl
        }
        encoded_key = key.encode() if isinstance(key, str) else key
        self.db[encoded_key] = json.dumps(entry).encode()
    
    # Get with expiration check
    def get(self, key, default=None):
        """Retrieve with TTL check - O(log n)"""
        encoded_key = key.encode() if isinstance(key, str) else key
        
        if encoded_key not in self.db:
            return default
        
        entry = json.loads(self.db[encoded_key].decode())
        
        # Check expiration
        if entry['ttl'] and time.time() - entry['time'] > entry['ttl']:
            del self.db[encoded_key]
            return default
        
        return entry['value']
    
    def close(self):
        """Close database - O(n)"""
        self.db.close()

# Usage
cache = PersistentCache()
cache.set('user:1', {'name': 'Alice', 'age': 30})
user = cache.get('user:1')
print(user)
cache.close()
```

### Counter Storage

```python
import dbm

class CounterStore:
    """Count things persistently"""
    
    def __init__(self, path='counters.db'):
        self.db = dbm.open(path, 'c')
    
    # Increment counter - O(log n)
    def increment(self, counter_name):
        key = counter_name.encode()
        
        current = int(self.db.get(key, b'0'))
        self.db[key] = str(current + 1).encode()
        
        return current + 1
    
    # Get counter - O(log n)
    def get(self, counter_name):
        key = counter_name.encode()
        return int(self.db.get(key, b'0'))
    
    def close(self):
        self.db.close()

# Usage
counters = CounterStore()
counters.increment('page_views')
counters.increment('page_views')
print(counters.get('page_views'))  # 2
counters.close()
```

### Configuration Storage

```python
import dbm
import json

class DBMConfig:
    """Store configuration in DBM"""
    
    def __init__(self, path='config.db'):
        self.db = dbm.open(path, 'c')
    
    # Save config - O(log n)
    def set(self, key, value):
        encoded_key = key.encode()
        encoded_value = json.dumps(value).encode()
        self.db[encoded_key] = encoded_value
    
    # Load config - O(log n)
    def get(self, key, default=None):
        encoded_key = key.encode()
        if encoded_key in self.db:
            return json.loads(self.db[encoded_key].decode())
        return default
    
    # Get all as dict - O(n)
    def get_all(self):
        return {
            key.decode(): json.loads(value.decode())
            for key, value in self.db.items()
        }
    
    def close(self):
        self.db.close()

# Usage
config = DBMConfig()
config.set('database.host', 'localhost')
config.set('database.port', 5432)
config.set('debug', True)

print(config.get('database.host'))
print(config.get_all())
config.close()
```

## Limitations and Alternatives

### DBM Limitations
- Keys and values must be bytes
- No complex queries
- Limited to key-value pairs
- Not suitable for relationships

### When to Use

```python
# Good for:
# - Simple persistent storage
# - Key-value pairs
# - Cache backends
# - Configuration storage

import dbm
db = dbm.open('simple_store')

# Better alternatives:
# - For structured data: sqlite3
# - For web applications: redis
# - For documents: MongoDB
# - For complex queries: PostgreSQL
```

## Comparison with Alternatives

### DBM vs Shelve

```python
# DBM: Lower level, faster, requires bytes
import dbm
db = dbm.open('data')
db[b'key'] = b'value'

# Shelve: Higher level, handles pickling, slower
import shelve
shelf = shelve.open('data')
shelf['key'] = {'complex': 'object'}
```

### DBM vs SQLite

```python
# DBM: Simple, fast, limited
import dbm
db = dbm.open('data')

# SQLite: Complex, slower, full querying
import sqlite3
conn = sqlite3.connect('data.db')
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS data...')
```

## Best Practices

### Do's
- Use shelve instead of dbm directly
- Encode strings to bytes explicitly
- Use context managers
- Close database when done
- Use appropriate backend

### Avoid's
- Don't store complex objects directly
- Don't share between processes without synchronization
- Don't iterate over keys repeatedly
- Don't use for large datasets

## Related Documentation

- [Shelve Module](shelve.md)
- [Pickle Module](pickle.md)
- [SQLite3 Module](sqlite3.md)
- [JSON Module](json.md)
