# JSON Module Complexity

The `json` module provides JSON serialization and deserialization.

## Functions

| Function | Time | Space | Notes |
|----------|------|-------|-------|
| `json.dumps(obj)` | O(n) | O(n) | Serialize to string |
| `json.dump(obj, fp)` | O(n) | O(1) streaming | Write to file |
| `json.loads(s)` | O(n) | O(n) | Parse JSON string |
| `json.load(fp)` | O(n) | O(n) | Read from file |
| `JSONEncoder.encode()` | O(n) | O(n) | Custom encoder |
| `JSONDecoder.decode()` | O(n) | O(n) | Custom decoder |

## Serialization (dumps/dump)

### Time Complexity: O(n)

Where n = total number of elements and size of strings in object tree.

```python
import json

# Simple object: O(n) where n = 3
data = {'a': 1, 'b': 2, 'c': 3}
json_str = json.dumps(data)  # O(3)

# Nested object: O(n) where n = total elements
data = {
    'users': [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25},
    ],
    'count': 2
}
json_str = json.dumps(data)  # O(n) for all elements
```

### Space Complexity: O(n)

```python
import json

# Memory usage proportional to output size
data = {'key': 'x' * 1000000}
json_str = json.dumps(data)  # O(n) - creates large string
# JSON includes: {"key":"xxx..."}
# Size ~ data size + quotes + braces
```

## Deserialization (loads/load)

### Time Complexity: O(n)

```python
import json

# Parsing JSON string: O(n) where n = string length
json_str = '{"key": "value", "num": 123}'
data = json.loads(json_str)  # O(n)

# Large JSON: O(n)
large_json = json.dumps({'data': [i for i in range(10000)]})
data = json.loads(large_json)  # O(n)
```

### Space Complexity: O(n)

```python
import json

# Creates Python objects taking O(n) space
json_str = '{"items": [1, 2, 3, ..., 10000]}'
data = json.loads(json_str)  # O(n) memory for result
```

## File I/O

### dump() - Write to File

```python
import json

# Write to file: O(n) for serialization + file I/O
data = {'key': 'value', 'items': list(range(1000))}

with open('data.json', 'w') as f:
    json.dump(data, f)  # O(n) serialization + write

# Streaming: O(1) memory, O(n) time
# Writes to file incrementally
```

### load() - Read from File

```python
import json

# Read from file: O(n) for parsing
with open('data.json', 'r') as f:
    data = json.load(f)  # O(n) parse time, O(n) memory
```

## Custom Encoders/Decoders

### JSONEncoder

```python
import json
from datetime import datetime

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):  # O(1) per call
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Use custom encoder: O(n) + O(1) per custom object
data = {'timestamp': datetime.now()}
json_str = json.dumps(data, cls=DateTimeEncoder)  # O(n)
```

### JSONDecoder

```python
import json
from datetime import datetime

def datetime_parser(dct):  # O(1) per call
    for key, val in dct.items():
        if isinstance(val, str):
            try:
                dct[key] = datetime.fromisoformat(val)
            except (ValueError, TypeError):
                pass
    return dct

# Use custom decoder: O(n) + O(1) per custom object
json_str = '{"timestamp": "2024-01-12T12:00:00"}'
data = json.loads(json_str, object_hook=datetime_parser)  # O(n)
```

## Performance Characteristics

### Best Practices

```python
import json

# Good: Single serialization
data = {'items': list(range(1000))}
json_str = json.dumps(data)  # O(n) once

# Bad: Multiple serializations
for i in range(100):
    json_str = json.dumps(data)  # O(n) * 100

# Good: Reuse encoder for large operations
encoder = json.JSONEncoder()
for i in range(100):
    json_str = encoder.encode(data)  # Still O(n) per iteration, but optimized
```

### Memory Efficiency

```python
import json

# Bad: Load entire large file into memory
with open('huge.json') as f:
    data = json.load(f)  # O(n) memory

# Better: Stream parsing (if available)
# or process line by line with JSONL format
with open('data.jsonl') as f:
    for line in f:
        obj = json.loads(line)  # O(1) per line
```

## Common Patterns

### Pretty Printing

```python
import json

data = {'key': 'value', 'nested': {'a': 1, 'b': 2}}

# Normal: O(n)
json_str = json.dumps(data)

# Pretty printed: O(n) (same complexity, different format)
json_str = json.dumps(data, indent=2, sort_keys=True)
```

### Custom Default Handler

```python
import json

def custom_serializer(obj):  # O(1) per object
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

person = Person('Alice', 30)
json_str = json.dumps(person, default=custom_serializer)  # O(n)
```

## Version Notes

- **Python 2.6+**: Basic json module
- **Python 3.4+**: Better performance
- **Python 3.6+**: Preserves key order (dicts ordered)
- **Python 3.9+**: Performance improvements

## Common Issues

### Large Files

```python
import json

# Problem: Memory usage for large files
# Solution: Stream or use generators

def process_large_json(filename):
    with open(filename) as f:
        # If it's a list, could parse item by item
        # Or use JSONL format (one JSON object per line)
        for line in f:
            obj = json.loads(line)
            yield obj
```

### Circular References

```python
import json

# This will fail with circular reference
a = {'name': 'A'}
b = {'name': 'B', 'ref': a}
a['ref'] = b  # Circular!

json.dumps(a)  # ValueError: Circular reference detected
```

## Related Documentation

- [Pickle Module](pickle.md) - For Python object serialization
- [CSV Module](csv.md) - For tabular data
