# Counter - Count Hashable Objects Complexity

The `Counter` class from `collections` provides a convenient way to count occurrences of hashable objects with specialized frequency analysis methods.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Counter()` | O(n) | O(n) | Create from iterable |
| `update()` | O(n) | O(n) | Add counts |
| `most_common(k)` | O(n log k) | O(k) | k-largest sorted |
| `subtract()` | O(n) | O(1) | Subtract counts |
| Lookup | O(1) | O(1) | Get count |

## Basic Usage

```python
from collections import Counter

# Create from iterable - O(n)
c = Counter([1, 2, 2, 3, 3, 3])  # O(6)
# Result: {3: 3, 2: 2, 1: 1}

# Create from string - O(n)
c = Counter('mississippi')  # O(11)
# Result: {'i': 4, 's': 4, 'p': 2, 'm': 1}

# Create from keyword args - O(n)
c = Counter(a=3, b=1)  # O(2)
# Result: {'a': 3, 'b': 1}
```

## Frequency Analysis

### Most Common

```python
from collections import Counter

text = "the quick brown fox jumps over the lazy dog"
words = text.split()

# Create counter - O(n)
word_count = Counter(words)  # O(9)

# Get most common - O(n log k)
top_5 = word_count.most_common(5)  # O(9 * log 5)
# Returns: [('the', 2), ('quick', 1), ('brown', 1), ...]

# Get all sorted - O(n log n)
sorted_all = word_count.most_common()  # O(n log n)

# Get least common
least = word_count.most_common()[-5:]  # O(n log n)
```

### Filtering Rare Items

```python
from collections import Counter

# Count items - O(n)
data = [1, 1, 2, 2, 2, 3, 3, 3, 3, 4]
c = Counter(data)  # O(10)

# Filter by frequency - O(n)
rare = {item: count for item, count in c.items() if count < 2}
# {4: 1}

# Keep only frequent items - O(n)
c = Counter(data)
for item in list(c):  # O(n)
    if c[item] < 3:   # O(1)
        del c[item]   # O(1)
```

## Counter Arithmetic

### Adding Counters

```python
from collections import Counter

# Create counters - O(n)
c1 = Counter(['a', 'b', 'c'])  # O(3)
c2 = Counter(['b', 'c', 'd'])  # O(3)

# Add - O(n)
combined = c1 + c2  # O(3+2) = O(5)
# Result: Counter({'b': 2, 'c': 2, 'a': 1, 'd': 1})

# Subtract - O(n)
diff = c1 - c2  # O(3)
# Result: Counter({'a': 1})

# Intersection (min) - O(n)
inter = c1 & c2  # O(3)
# Result: Counter({'b': 1, 'c': 1})

# Union (max) - O(n)
union = c1 | c2  # O(3)
# Result: Counter({'b': 1, 'c': 1, 'a': 1, 'd': 1})
```

### In-place Operations

```python
from collections import Counter

c1 = Counter(['a', 'b', 'c'])
c2 = Counter(['b', 'c', 'd'])

# Update (add counts) - O(n)
c1.update(c2)  # O(n) - modifies c1
# Result: Counter({'b': 2, 'c': 2, 'a': 1, 'd': 1})

# Subtract (subtract counts) - O(n)
c1.subtract(c2)  # O(n) - modifies c1
```

## Common Patterns

### Word Frequency Analysis

```python
from collections import Counter

text = "the quick brown fox jumps over the lazy dog the fox"

# Split and count - O(n)
words = text.split()  # O(n)
word_freq = Counter(words)  # O(n)

# Get most common 3 - O(n log k)
top_3 = word_freq.most_common(3)
# [('the', 3), ('fox', 2), ('quick', 1)]

# What words appear more than once?
frequent = [word for word, count in word_freq.items() if count > 1]
# ['the', 'fox']
```

### Anagram Finding

```python
from collections import Counter

def are_anagrams(word1, word2):
    """Check if two words are anagrams - O(n)"""
    return Counter(word1) == Counter(word2)  # O(n)

# Usage - O(n)
print(are_anagrams("listen", "silent"))  # True
print(are_anagrams("hello", "world"))    # False

# Group anagrams - O(n*m log m)
def group_anagrams(words):
    """Group words by anagram - O(n*m log m)"""
    anagrams = {}
    for word in words:  # O(n)
        signature = ''.join(sorted(word))  # O(m log m) - m = word length
        if signature not in anagrams:
            anagrams[signature] = []
        anagrams[signature].append(word)
    return anagrams
```

### Find Missing/Duplicate Elements

```python
from collections import Counter

# Find duplicates - O(n)
numbers = [1, 2, 2, 3, 3, 3, 4]
counts = Counter(numbers)  # O(n)

duplicates = {num: count for num, count in counts.items() if count > 1}
# {2: 2, 3: 3}

# Find missing in range - O(n)
expected = set(range(1, 8))  # O(7)
actual = set(numbers)  # O(n)
missing = expected - actual  # O(7)
# {5, 6, 7}
```

## Comparison with defaultdict(int)

```python
from collections import Counter, defaultdict

data = [1, 2, 2, 3, 3, 3]

# Counter - O(n)
c = Counter(data)  # O(6)
print(c.most_common(2))  # Most common 2 items

# defaultdict(int) - O(n)
dd = defaultdict(int)
for x in data:  # O(n)
    dd[x] += 1
# Must manually sort for most_common

# Use Counter for frequency analysis
# Use defaultdict(int) for general counting
```

## When to Use Counter

### Good For:
- Word frequency analysis
- Finding duplicates
- Frequency sorting
- Anagram detection
- Element counting with analysis

### Not Good For:
- Simple counting loops (slightly slower)
- Non-hashable items
- When you don't need frequency methods
- Space-constrained environments

## Accessing Counts

```python
from collections import Counter

c = Counter(['a', 'b', 'b', 'c', 'c', 'c'])

# Get count - O(1)
print(c['a'])  # 1
print(c['d'])  # 0 (missing keys return 0, not KeyError)

# Get with get() - O(1)
print(c.get('a'))  # 1
print(c.get('d'))  # None

# Check existence - O(1)
if 'a' in c:  # O(1)
    print(c['a'])
```

## Version Notes

- **Python 2.7+**: Counter available
- **Python 3.x**: Same functionality
- **Python 3.10+**: Better performance improvements

## Related Modules

- **[defaultdict](defaultdict.md)** - Dict with defaults
- **[OrderedDict](ordereddict.md)** - Insertion-order dict
- **[collections](collections.md)** - Container data types

## Best Practices

✅ **Do**:
- Use for frequency analysis
- Use most_common() for top-k
- Use Counter arithmetic for operations
- Use for anagram/duplicate detection

❌ **Avoid**:
- For non-hashable objects
- When simple dict suffices
- Excessive Counter creation (reuse)
- When space efficiency critical
