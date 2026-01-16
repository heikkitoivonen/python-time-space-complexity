# hash() Function Complexity

The `hash()` function returns the hash value of an object, which is used by dictionaries and sets for fast lookups.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `hash(object)` | O(k) | O(1) | k = object size |
| Hash of immutable | O(k) | O(1) | e.g., int, str, tuple |
| Hash of mutable | Error | - | e.g., list, dict, set (unhashable) |
| Dictionary lookup | O(1) avg | O(1) | O(n) worst case |
| Set membership | O(1) avg | O(1) | O(n) worst case |

## Hash Basics

### Creating Hashes

```python
# Hash immutable types - O(k) where k = object size
hash(42)                    # O(1) - small integer
hash(3.14)                  # O(1) - float
hash("hello")               # O(5) - string length
hash((1, 2, 3))            # O(3) - tuple size

# Same value = same hash
hash("hello") == hash("hello")  # True

# Different values = different hash (usually)
hash("hello") != hash("world")  # Usually true
```

### Unhashable Types

```python
# Lists are unhashable (mutable)
try:
    hash([1, 2, 3])  # TypeError!
except TypeError as e:
    print("unhashable type: 'list'")

# Dictionaries are unhashable
try:
    hash({'a': 1})  # TypeError!
except TypeError:
    print("unhashable type: 'dict'")

# Sets are unhashable
try:
    hash({1, 2, 3})  # TypeError!
except TypeError:
    print("unhashable type: 'set'")

# Frozen sets ARE hashable
hash(frozenset([1, 2, 3]))  # OK - O(3)
```

## Hash-based Collections

### Dictionary Lookups

```python
# Dictionary uses hash for O(1) lookup
d = {'key1': 'value1', 'key2': 'value2'}

# Lookup - O(1) average case
value = d['key1']  # O(1) - uses hash('key1')

# Insert - O(1) average case
d['key3'] = 'value3'  # O(1) - uses hash('key3')

# Delete - O(1) average case
del d['key1']  # O(1) - uses hash('key1')

# Membership - O(1) average case
if 'key2' in d:  # O(1) - uses hash('key2')
    pass
```

### Set Operations

```python
# Set uses hash for O(1) membership
s = {1, 2, 3, 4, 5}

# Add - O(1) average
s.add(6)  # O(1) - uses hash(6)

# Remove - O(1) average
s.discard(3)  # O(1) - uses hash(3)

# Membership - O(1) average
if 4 in s:  # O(1) - uses hash(4)
    pass

# Set intersection (requires hashing) - O(min(len(s1), len(s2)))
s1 = {1, 2, 3}
s2 = {2, 3, 4}
result = s1 & s2  # O(min(3, 3)) = O(3)
```

## Hash Values

### Hash Stability

```python
# Python 3.3+: Hash randomization enabled
# Same object, same hash within session
x = 42
h1 = hash(x)
h2 = hash(x)
h1 == h2  # True - within same Python session

# Different sessions may have different hashes
# This prevents hash collision attacks

# Strings hash differently each session (Python 3.3+)
h1 = hash("hello")
# Restart Python
h2 = hash("hello")  # Different value (secure)
```

### Hash Collisions

```python
# Different values can have same hash (collision)
# Dictionaries handle this with probing or chaining

# Example: hash collision (rare)
# If hash(obj1) == hash(obj2), dict stores both
# and compares keys for equality

d = {}
d['a'] = 1
d['b'] = 2

# Even if hash('a') == hash('b'),
# d['a'] is still unique because 'a' != 'b'
```

## Custom Hashing

### __hash__ and __eq__

```python
# Custom hashable class
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def __hash__(self):
        # Must return hash of immutable representation
        return hash((self.name, self.age))  # O(name_len + 1)
    
    def __eq__(self, other):
        # If hash same, equality test used to confirm
        if not isinstance(other, Person):
            return False
        return self.name == other.name and self.age == other.age  # O(name_len)

# Usage
p = Person('Alice', 30)
s = {p}  # Can add to set - uses __hash__()
d = {p: 'data'}  # Can use as key - uses __hash__()
```

### Important Rule: __hash__ and __eq__ Agreement

```python
# Rule: if a == b, then hash(a) == hash(b)

class GoodClass:
    def __init__(self, value):
        self.value = value
    
    def __eq__(self, other):
        return self.value == other.value
    
    def __hash__(self):
        return hash(self.value)

# Rule follows: equal objects have equal hashes
a = GoodClass(5)
b = GoodClass(5)
assert a == b  # True
assert hash(a) == hash(b)  # True - good!

class BadClass:
    def __init__(self, value):
        self.value = value
    
    def __eq__(self, other):
        return self.value == other.value
    
    def __hash__(self):
        return 42  # Wrong! Not based on value

# Rule violated: equal objects don't have equal hashes
a = BadClass(5)
b = BadClass(5)
assert a == b  # True
assert hash(a) == hash(b)  # True (both 42) but coincidence!
d = {a: 1}
d[b] += 1  # Oops, creates new key instead of updating!
```

## Hashing Different Types

### Immutable Types

```python
# All hashable efficiently - O(size)
hash(None)             # O(1) - special case
hash(True)             # O(1) - boolean
hash(42)               # O(1) - small integer
hash(12345678901234)   # O(1) - large integer  
hash(3.14)             # O(1) - float
hash("hello")          # O(5) - string length
hash(b"hello")         # O(5) - bytes length
hash((1, 2, 3))        # O(3) - tuple depth
hash(frozenset([1,2])) # O(2) - frozenset size
```

### Integers

```python
# Integer hashing - O(1)
hash(0)      # 0
hash(1)      # 1
hash(-1)     # -2
hash(256)    # 256

# Small integers cached for performance
# hash(n) usually returns n itself for small values

# Large integers
big = 10**100
hash(big)  # O(1) due to Python's optimization
```

### Strings

```python
# String hashing - O(len(string))
hash("")      # O(0)
hash("a")     # O(1)
hash("hello") # O(5)

# String intern: equal strings have equal hashes
s1 = "hello"
s2 = "hello"
hash(s1) == hash(s2)  # True - O(5)
```

### Tuples

```python
# Tuple hashing combines element hashes - O(tuple_size)
hash((1,))         # O(1)
hash((1, 2, 3))    # O(3) - hashes all elements
hash(())           # O(0) - empty tuple

# If tuple contains unhashable, fails
try:
    hash((1, [2, 3]))  # TypeError! list is unhashable
except TypeError:
    pass
```

## Using Hash for Caching

### Memoization with Hash

```python
# Cache expensive computation using hash
cache = {}

def expensive_function(arg):
    key = hash(arg)  # O(k) for hashing
    
    if key in cache:  # O(1) lookup
        return cache[key]
    
    result = do_expensive_work(arg)  # Slow
    cache[key] = result  # O(1) store
    return result

# Multiple calls with same hash are instant
result1 = expensive_function(("data", 1))  # Computed
result2 = expensive_function(("data", 1))  # From cache O(1)
```

### Set Deduplication

```python
# Remove duplicates using hash - O(n)
numbers = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4]
unique = set(numbers)  # O(n) - uses hash for each

# For unhashable types, need different approach
data = [[1, 2], [1, 2], [3, 4]]
# Can't use set directly
# Instead convert to hashable:
unique = set(tuple(d) for d in data)  # O(n)
```

## Performance Notes

### Hash Collisions and Worst Case

```python
# Average case: O(1) dictionary access
# Worst case: O(n) if all items hash to same value

# Python mitigates this with:
# 1. Good hash functions
# 2. Randomized hashing (Python 3.3+)
# 3. Open addressing or chaining

# You shouldn't encounter O(n) in practice
d = {}
for i in range(1000):
    d[i] = i  # O(1) each, not O(n)
```

### Hash vs Equality

```python
# Hash is used first for efficiency
# If hash matches, equality check confirms

# This matters for custom classes:
class Efficient:
    def __init__(self, data):
        self.data = data
    
    def __hash__(self):
        return 42  # All same hash
    
    def __eq__(self, other):
        return self.data == other.data  # Expensive comparison
        # Only called if hashes match

# With 1000 unique objects:
s = {Efficient(i) for i in range(1000)}
# Each insertion: O(1) hash, then O(1) equality
# Total: O(1000) insertions, each O(1) if no collisions
```

## Avoiding Hashing

### Use frozenset Instead of set

```python
# For hashable collections, use frozenset
frozen = frozenset([1, 2, 3])
hash(frozen)  # Works! Can use as dict key

# Mutable set can't be hashed
regular = {1, 2, 3}
try:
    hash(regular)  # TypeError!
except TypeError:
    pass

# So frozenset can be dict key/set member
d = {frozenset([1, 2]): 'value'}  # Works
s = {frozenset([3, 4])}  # Works
```

## Version Notes

- **Python 2.x**: Different hash implementation
- **Python 3.3+**: Hash randomization for security
- **All versions**: Hash of immutable types is stable

## Related Functions

- **[id()](builtins/id.md)** - Object identity (different from hash)
- **[set()](builtins/set.md)** - Uses hash for membership
- **[dict](builtins/dict.md)** - Uses hash for key lookup

## Best Practices

✅ **Do**:
- Implement `__hash__()` and `__eq__()` together for custom classes
- Ensure hash agrees with equality: if `a == b` then `hash(a) == hash(b)`
- Use frozen data structures for dict keys/set members
- Use frozenset instead of set when you need hashability

❌ **Avoid**:
- Implementing `__hash__()` without `__eq__()` (or vice versa)
- Relying on specific hash values (they can change between Python versions)
- Hashing mutable objects (they're unhashable by design)
- Implementing `__hash__()` that depends on mutable state
- Assuming hash(a) == hash(b) means a == b (can be false due to collisions)
