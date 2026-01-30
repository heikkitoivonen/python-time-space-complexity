# shelve Module Complexity

The `shelve` module provides persistent dictionary storage using the DBM database backend, allowing Python objects to be stored and retrieved from disk efficiently.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `shelve.open()` | O(1) | O(1) | Open/create database; filesystem work varies |
| `shelf[key] = value` | O(1) avg, O(n) worst | O(k) | DBM lookup + pickle; backend-dependent |
| `shelf[key]` | O(1) avg, O(n) worst | O(k) | DBM lookup + unpickle; backend-dependent |
| `del shelf[key]` | O(1) avg, O(n) worst | O(1) | Delete key; backend-dependent |
| `key in shelf` | O(1) avg, O(n) worst | O(1) | Membership check; backend-dependent |
| `len(shelf)` | Varies | O(1) | Some backends scan keys (O(n)) |
| `shelf.keys()` | O(n) | O(n) | Often returns a materialized list; backend-dependent |
| `shelf.close()` | O(m) | O(1) | Flush pending writes (m = dirty entries) |

## Basic Usage

### Create and Store

```python
import shelve

# Open or create database - O(1) (filesystem work varies)
shelf = shelve.open('mydata.db')

# Store objects - O(1) avg per DBM operation
shelf['name'] = 'Alice'
shelf['age'] = 30
shelf['scores'] = [95, 87, 92]
shelf['config'] = {'debug': True, 'timeout': 30}

# Changes are buffered until close
shelf.close()  # O(m) - flush pending writes
```

### Retrieve Data

```python
import shelve

# Open existing database - O(1) (filesystem work varies)
shelf = shelve.open('mydata.db')

# Retrieve objects - O(1) avg per DBM operation
name = shelf['name']        # 'Alice'
age = shelf['age']          # 30
scores = shelf['scores']    # [95, 87, 92]

# Check existence - O(1) avg
if 'name' in shelf:
    print(f"Hello {shelf['name']}")

# Get with default - O(1) avg
email = shelf.get('email', 'no-email')

shelf.close()
```

## Context Manager Usage

### Automatic Cleanup

```python
import shelve

# Use with statement for automatic close (flush cost varies)
with shelve.open('mydata.db') as shelf:
    
    # Store data - O(1) avg
    shelf['user'] = {'name': 'Bob', 'age': 25}
    
    # Retrieve data - O(1) avg
    user = shelf['user']
    print(user)

# Automatically closed and flushed
```

## Iteration and Keys

### Iterate Over Keys

```python
import shelve

with shelve.open('mydata.db') as shelf:
    
# Store multiple items - O(1) avg each
shelf['user1'] = {'name': 'Alice'}
    shelf['user2'] = {'name': 'Bob'}
    shelf['user3'] = {'name': 'Charlie'}
    
    # Get all keys - O(n)
    keys = shelf.keys()
    for key in keys:
        print(f"{key}: {shelf[key]}")
    
    # Iterate directly - O(n)
    for key in shelf:
        print(f"{key}: {shelf[key]}")
    
# Number of items - varies by backend
count = len(shelf)
```

### Iterate Over Items

```python
import shelve

with shelve.open('mydata.db') as shelf:
    
    # Store data
    shelf['a'] = [1, 2, 3]
    shelf['b'] = [4, 5, 6]
    shelf['c'] = [7, 8, 9]
    
    # Iterate items - O(n)
    for key, value in shelf.items():
        print(f"{key}: {value}")
    
    # Get all values - O(n)
    values = shelf.values()
    for v in values:
        print(v)
```

## Modifications and Deletion

### Update Values

```python
import shelve

with shelve.open('mydata.db') as shelf:
    
    # Store initial data - O(1) avg
    shelf['counter'] = 0
    
    # Modify in-place - need to reassign - O(1) avg
    counter = shelf['counter']
    counter += 1
    shelf['counter'] = counter  # Reassign required
    
    # Modify list in-place won't work
    shelf['scores'] = [1, 2, 3]
    shelf['scores'].append(4)  # Changes don't persist!
    shelf['scores'] = [1, 2, 3, 4]  # Must reassign
    
    # Modify dictionary - need reassign - O(1) avg
    config = shelf['config']
    config['debug'] = False
    shelf['config'] = config  # Must reassign
```

### Delete Keys

```python
import shelve

with shelve.open('mydata.db') as shelf:
    
    # Store items
    shelf['temp1'] = 'data1'
    shelf['temp2'] = 'data2'
    shelf['keep'] = 'data3'
    
    # Delete key - O(1) avg
    del shelf['temp1']
    del shelf['temp2']
    
    # Delete with check - O(1) avg
    if 'temp1' in shelf:
        del shelf['temp1']
    
    # Remaining key
    print(shelf['keep'])  # 'data3'
```

## Database Options

### Specify Backend

```python
import shelve

# Use default backend selected by dbm
shelf = shelve.open('data')

# Explicitly specify backend
import dbm.dumb
import dbm.gnu

# dbm.dumb (pure Python, slow)
shelf = shelve.open('data', flag='c')

# Check available DBM modules
import dbm
print(dbm.whichdb('data'))  # Detect backend
```

### Open Flags

```python
import shelve

# 'r' = read-only
shelf = shelve.open('data.db', flag='r')

# 'w' = read-write, create if missing
shelf = shelve.open('data.db', flag='w')

# 'c' = read-write, create if missing (default)
shelf = shelve.open('data.db', flag='c')

# 'n' = always create new, empty
shelf = shelve.open('data.db', flag='n')
```

## Object Compatibility

### Pickleable Objects

```python
import shelve

with shelve.open('objects.db') as shelf:
    
    # Primitive types - O(1) avg DBM + O(k) pickle
    shelf['int'] = 42
    shelf['str'] = 'hello'
    shelf['list'] = [1, 2, 3]
    shelf['dict'] = {'a': 1, 'b': 2}
    shelf['tuple'] = (1, 2, 3)
    
    # Complex objects - O(1) avg DBM + O(k) pickle
    shelf['set'] = {1, 2, 3}
    shelf['bytes'] = b'binary'
    
    # Nested structures - O(1) avg DBM + O(k) pickle
    shelf['complex'] = {
        'data': [1, 2, 3],
        'config': {'debug': True},
        'items': [(1, 'a'), (2, 'b')]
    }
```

### Custom Classes

```python
import shelve

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def __repr__(self):
        return f"Person({self.name}, {self.age})"

with shelve.open('people.db') as shelf:
    
    # Store custom object - O(1) avg DBM + O(k) pickle
    shelf['person1'] = Person('Alice', 30)
    shelf['person2'] = Person('Bob', 25)
    
    # Retrieve and use - O(1) avg DBM + O(k) unpickle
    person = shelf['person1']
    print(person)  # Person(Alice, 30)
    print(person.age)  # 30
```

## Performance Considerations

### Time Complexity
- **Storage operations**: O(1) avg for DBM backends + disk I/O
- **Retrieval**: O(1) avg + unpickling time
- **Iteration**: O(n) to scan all keys
- **Deletion**: O(1) avg for DBM backends

### Space Complexity
- **Database**: O(n) for n stored objects
- **Memory**: Objects loaded on demand, cached

### Buffering and Flushing

```python
import shelve

shelf = shelve.open('data.db')

# Store items - buffered - O(1) avg per item
for i in range(1000):
    shelf[f'key{i}'] = f'value{i}'

# Data not written to disk yet!
# Force flush - O(m) for pending writes
shelf.sync()

# More safe: flush before reading in another process
shelf.sync()

# Close also flushes - O(m)
shelf.close()
```

## Common Patterns

### Cache Implementation

```python
import shelve
import time

class Cache:
    """Simple persistent cache"""
    
    def __init__(self, db_path='cache.db'):
        self.shelf = shelve.open(db_path)
    
    # Store with optional TTL
    def set(self, key, value, ttl=None):
        """Cache value - O(1) avg"""
        entry = {
            'value': value,
            'time': time.time(),
            'ttl': ttl
        }
        self.shelf[key] = entry
        self.shelf.sync()
    
    # Retrieve with expiration check
    def get(self, key, default=None):
        """Get cached value - O(1) avg"""
        if key not in self.shelf:
            return default
        
        entry = self.shelf[key]
        
        # Check expiration
        if entry['ttl'] and time.time() - entry['time'] > entry['ttl']:
            del self.shelf[key]
            return default
        
        return entry['value']

# Usage
cache = Cache()
cache.set('user:1', {'name': 'Alice'})
user = cache.get('user:1')
```

### Session Storage

```python
import shelve
import json

class SessionStore:
    """Store web session data"""
    
    def __init__(self, path='sessions.db'):
        self.shelf = shelve.open(path)
    
    # Create session - O(1) avg
    def create_session(self, session_id, data):
        self.shelf[session_id] = {
            'data': data,
            'created': time.time()
        }
        self.shelf.sync()
    
    # Get session - O(1) avg
    def get_session(self, session_id):
        if session_id in self.shelf:
            return self.shelf[session_id]['data']
        return None
    
    # Update session - O(1) avg
    def update_session(self, session_id, data):
        if session_id in self.shelf:
            session = self.shelf[session_id]
            session['data'].update(data)
            self.shelf[session_id] = session
            self.shelf.sync()
    
    # Delete session - O(1) avg
    def delete_session(self, session_id):
        if session_id in self.shelf:
            del self.shelf[session_id]
            self.shelf.sync()

# Usage
store = SessionStore()
store.create_session('abc123', {'user_id': 1, 'role': 'admin'})
```

### Configuration Storage

```python
import shelve
import json

class ConfigStore:
    """Persistent configuration"""
    
    def __init__(self, path='config.db'):
        self.shelf = shelve.open(path)
    
    # Save config - O(1) avg
    def save(self, key, value):
        self.shelf[key] = value
        self.shelf.sync()
    
    # Load config - O(1) avg
    def load(self, key, default=None):
        return self.shelf.get(key, default)
    
    # Load all - O(n)
    def load_all(self):
        return dict(self.shelf)
    
    # Remove - O(1) avg
    def remove(self, key):
        if key in self.shelf:
            del self.shelf[key]
            self.shelf.sync()

# Usage
config = ConfigStore()
config.save('database.host', 'localhost')
config.save('database.port', 5432)
host = config.load('database.host')
```

## Limitations and Alternatives

### Limitations
- Not thread-safe for concurrent writes
- Object must be pickleable
- Limited query capabilities
- Not suitable for large-scale data

### Alternatives

```python
# For simple cases: pickle
import pickle
with open('data.pkl', 'wb') as f:
    pickle.dump(data, f)

# For larger data: SQLite
import sqlite3
conn = sqlite3.connect('data.db')
cursor = conn.cursor()

# For web applications: Redis
import redis
client = redis.Redis()
client.set('key', 'value')

# For complex queries: PostgreSQL/MySQL
# Use SQLAlchemy or psycopg2
```

## Best Practices

### Do's
- Use context manager (with statement)
- Call sync() before other processes read
- Use for simple persistent storage
- Test data pickling compatibility

### Avoid's
- Don't share between processes without syncing
- Don't store non-pickleable objects
- Don't use for large datasets
- Don't modify mutable objects in-place

## Related Documentation

- [Pickle Module](pickle.md)
- [DBM Module](dbm.md)
- [SQLite3 Module](sqlite3.md)
- [JSON Module](json.md)
