# pickle Module Complexity

The `pickle` module serializes and deserializes Python objects into bytes, enabling object persistence and network transmission while maintaining Python semantics.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pickle.dumps(obj)` | O(n) | O(n) | Serialize to bytes, n = object size |
| `pickle.loads(data)` | O(n) | O(n) | Deserialize from bytes, n = data size |
| `dump()` to file | O(n) | O(n) | n = object size, requires memoization for object graph |
| `load()` from file | O(n) | O(n) | n = object size, loads all |
| Circular reference handling | O(n) | O(n) | Memoization tracks visited objects |

## Basic Pickling

### Simple Object Serialization

```python
import pickle

# Create object - O(1)
data = {'name': 'Alice', 'age': 30, 'scores': [95, 87, 92]}

# Serialize to bytes - O(n) where n = object size
pickled = pickle.dumps(data)
print(type(pickled))  # <class 'bytes'>
print(len(pickled))   # Size varies by protocol and data

# Deserialize from bytes - O(n)
restored = pickle.loads(pickled)
print(restored)       # {'name': 'Alice', 'age': 30, 'scores': [95, 87, 92]}
```

### File Persistence

```python
import pickle

# Serialize to file - O(n)
data = [1, 2, 3, 4, 5]
with open('data.pkl', 'wb') as f:
    pickle.dump(data, f)  # O(n) streaming

# Deserialize from file - O(n)
with open('data.pkl', 'rb') as f:
    restored = pickle.load(f)  # O(n) reads all
    print(restored)  # [1, 2, 3, 4, 5]
```

## Pickle Protocols

### Protocol Versions

```python
import pickle

obj = {'a': 1, 'b': [2, 3, 4]}

# Protocol 0 (ASCII, human-readable) - O(n)
p0 = pickle.dumps(obj, protocol=0)
print(len(p0))  # Often largest, but varies by object

# Protocol 1 (Binary, old) - O(n)
p1 = pickle.dumps(obj, protocol=1)
print(len(p1))  # Often smaller than protocol 0

# Protocol 2 (Binary, Python 2.3+) - O(n)
p2 = pickle.dumps(obj, protocol=2)
print(len(p2))  # Often smaller than protocol 1

# Protocol 3 (Binary, Python 3.0+) - O(n)
p3 = pickle.dumps(obj, protocol=3)
print(len(p3))  # Often smaller than protocol 2

# Protocol 4 (Binary, Python 3.4+) - O(n)
p4 = pickle.dumps(obj, protocol=4)
print(len(p4))  # Often more compact for many objects

# Protocol 5 (Binary, Python 3.8+) - O(n)
p5 = pickle.dumps(obj, protocol=5)
print(len(p5))  # Supports out-of-band buffers; size varies
```

### Default Protocol

```python
import pickle
import sys

# Default protocol depends on Python version
default = pickle.DEFAULT_PROTOCOL
print(f"Default: {default}")  # 3, 4, or 5 depending on version

# Highest protocol available
highest = pickle.HIGHEST_PROTOCOL
print(f"Highest: {highest}")  # 5 in Python 3.8+

# For compatibility, specify protocol explicitly
data = {'key': 'value'}
p_compat = pickle.dumps(data, protocol=3)  # Python 3.0+ compatible
```

## Custom Serialization

### __getstate__ and __setstate__

```python
import pickle

class Person:
    def __init__(self, name, age, password):
        self.name = name
        self.age = age
        self.password = password  # Sensitive, don't pickle
    
    # Called during pickling - O(1)
    def __getstate__(self):
        # Return what to pickle
        state = self.__dict__.copy()
        del state['password']  # Exclude password
        return state
    
    # Called during unpickling - O(1)
    def __setstate__(self, state):
        self.__dict__.update(state)
        self.password = None  # Set default

# Pickle - O(n)
person = Person('Alice', 30, 'secret123')
pickled = pickle.dumps(person)

# Unpickle - O(n)
restored = pickle.loads(pickled)
print(restored.name)      # 'Alice'
print(restored.password)  # None (not stored)
```

### reduce() Method

```python
import pickle

class CustomObject:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    # Called during pickling - O(1)
    def __reduce__(self):
        # Return (callable, args) to recreate object
        return (CustomObject, (self.x, self.y))

# Pickle - O(n)
obj = CustomObject(10, 20)
pickled = pickle.dumps(obj)

# Unpickle - O(n)
restored = pickle.loads(pickled)
print(restored.x, restored.y)  # 10 20
```

## Complex Object Types

### Circular References

```python
import pickle

# Create circular reference
node1 = {'name': 'A', 'next': None}
node2 = {'name': 'B', 'next': None}
node1['next'] = node2
node2['next'] = node1  # Circular

# Pickle handles with memoization - O(n)
pickled = pickle.dumps(node1)

# Unpickle reconstructs structure - O(n)
restored = pickle.loads(pickled)
print(restored['name'])           # 'A'
print(restored['next']['name'])   # 'B'
print(restored['next']['next'] is restored)  # True (circular preserved)
```

### Class Instances

```python
import pickle

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"

# Pickle - O(n)
p = Point(3, 4)
pickled = pickle.dumps(p)

# Unpickle - O(n) (requires class accessible)
restored = pickle.loads(pickled)
print(restored)         # Point(3, 4)
print(type(restored))   # <class '__main__.Point'>
```

### Nested Objects

```python
import pickle

class Team:
    def __init__(self, name, members):
        self.name = name
        self.members = members  # List of dicts

# Pickle nested structure - O(n) in total object graph size
team = Team('Team A', [
    {'name': 'Alice', 'role': 'lead'},
    {'name': 'Bob', 'role': 'dev'}
])

pickled = pickle.dumps(team)

# Unpickle - O(n) in total object graph size
restored = pickle.loads(pickled)
print(restored.name)       # 'Team A'
print(restored.members[0]) # {'name': 'Alice', ...}
```

## Performance and Size

### Protocol Comparison

```python
import pickle
import sys

# Create test object
test_data = {
    'strings': ['a' * 100 for _ in range(10)],
    'numbers': list(range(1000)),
    'nested': [{'id': i, 'value': i**2} for i in range(100)]
}

# Compare sizes
sizes = {}
for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
    pickled = pickle.dumps(test_data, protocol=protocol)
    sizes[protocol] = len(pickled)
    print(f"Protocol {protocol}: {len(pickled)} bytes")

# Higher protocols typically produce smaller output
```

### Large Object Serialization

```python
import pickle
import io

# Large list - O(n)
large_list = list(range(1000000))

# Method 1: dumps - creates bytes in memory - O(n) space
data_bytes = pickle.dumps(large_list)  # Large memory usage

# Method 2: dump to file - streams output - O(n) time, O(n) space for memoization
with open('large.pkl', 'wb') as f:
    pickle.dump(large_list, f)  # Much more memory efficient

# Method 3: Pickler with file - O(n) time, O(n) space for memoization
with open('large.pkl', 'wb') as f:
    pickler = pickle.Pickler(f)
    pickler.dump(large_list)
```

## Unpickler Customization

### Custom Unpickler

```python
import pickle

# Version migration on unpickle
class VersionedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Intercept class loading - O(1)
        if module == 'old_module':
            module = 'new_module'
        return super().find_class(module, name)

# Usage
data = b'...'  # Pickled data
with open('old_data.pkl', 'rb') as f:
    unpickler = VersionedUnpickler(f)
    obj = unpickler.load()
```

## Security Considerations

### Dangerous Unpickling

```python
import pickle

# ⚠️ SECURITY RISK: Never unpickle untrusted data!
# Pickle can execute arbitrary code during unpickling

# Unsafe - could execute malicious code
untrusted_data = b'...'  # From network/user
# obj = pickle.loads(untrusted_data)  # DANGEROUS!

# Safe: Use alternative formats for untrusted data
import json
safe_data = json.loads(untrusted_string)  # JSON is safe
```

### Restrict Classes

```python
import pickle
import io

class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Only allow specific classes - O(1)
        if module == 'my_app' and name in ['SafeClass', 'Data']:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"Forbidden: {module}.{name}")

# Use restricted unpickler
data = b'...'
with io.BytesIO(data) as f:
    unpickler = RestrictedUnpickler(f)
    obj = unpickler.load()
```

## Pickle Alternatives

### JSON (Safe Alternative)

```python
import json

# JSON is safe but limited
data = {'name': 'Alice', 'age': 30}

# Serialize - O(n)
json_str = json.dumps(data)

# Deserialize - O(n)
restored = json.loads(json_str)

# Advantages:
# - Human readable
# - Language independent
# - Safe (no code execution)
# - Limited types (no custom classes)
```

### Dill (Extended Pickling)

```python
# pip install dill

import dill

# Dill extends pickle to handle more types
def my_function(x):
    return x ** 2

# Can pickle functions - O(n)
pickled = dill.dumps(my_function)
restored = dill.loads(pickled)

# Standard pickle cannot pickle functions
```

## Performance Notes

### Time Complexity
- **dumps()**: O(n) where n = total size of object graph
- **loads()**: O(n) where n = size of pickled data
- **Circular reference handling**: O(n) with memoization

### Space Complexity
- **dumps()**: O(n) creates bytes representation
- **loads()**: O(n) creates deserialized objects
- **dump()/load()**: Streaming reduces memory for file I/O

### Protocol Selection
- **Protocol 0**: Slowest, largest, ASCII (rarely use)
- **Protocol 1-2**: Legacy compatibility
- **Protocol 3**: Default Python 3, good balance
- **Protocol 4+**: More compact encoding (no compression), often faster for large objects

## Best Practices

### Do's
- Use protocol 4+ for new code (Python 3.4+)
- Implement __getstate__ for security/control
- Use file I/O for large objects
- Use json/yaml for inter-language data

### Avoid's
- Never unpickle untrusted data
- Don't pickle sensitive data
- Don't rely on pickle for long-term storage (fragile across versions)
- Don't use pickle for inter-process communication across Python versions

## Related Documentation

- [JSON Module](json.md)
- [Copy Module](copy.md)
- [Shelve Module](shelve.md)
- [CSV Module](csv.md)

## Further Reading

- [CPython Internals: pickle](https://zpoint.github.io/CPython-Internals/Modules/pickle/pickle.html) -
  Deep dive into CPython's pickle implementation
