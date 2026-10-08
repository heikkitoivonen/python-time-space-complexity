# defaultdict Complexity

`collections.defaultdict` is a `dict` subclass that fills in a missing key when it is read:
`dd[key]` on an absent key calls `default_factory()`, stores the result under the key and returns
it. Lookups and updates are the inherited `dict` code, so a hit is a `dict` lookup and a miss adds
one factory call and one insertion.

`n` is the keys in the `defaultdict`, `m` is the entries supplied by the other mapping, iterable or
keyword arguments an operation takes, and `f` is the cost of one call to `default_factory`, both
the time it takes and the value it returns. Bounds treat hashing a key and comparing keys or values
as O(1).

## Complexity Reference

### defaultdict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `defaultdict(default_factory=None, /, *args, **kwargs)` | O(m) | O(m) | The remaining arguments go to `dict()`; a first argument that is neither callable nor `None` raises `TypeError` |
| `dd[key]`, key present | O(1) | O(1) | The factory is not called |
| `dd[key]`, key missing | O(1 + f) amortized | O(1 + f) amortized | Calls `__missing__`, which stores and returns the factory's value; with no factory it raises `KeyError` |
| `dd[key] += 1` | O(1 + f) amortized | O(1 + f) amortized | A read and a store; on a missing key the read stores the factory's value first |
| `defaultdict.__missing__(key)` | O(1 + f) amortized | O(1 + f) amortized | What `dd[key]` calls on a miss; `get()`, `in`, `setdefault()` and `pop()` never call it |
| `defaultdict.default_factory` | O(1) | O(1) | Read or reassign at any time; `None` makes a miss raise `KeyError` |
| `defaultdict.copy()`, `copy.copy(dd)` | O(n) | O(n) | Shallow; the copy keeps the same factory |
| `dd \| other`, `other \| dd` | O(n + m) | O(n + m) | A new `defaultdict` with the factory of the `defaultdict` operand, the left one if both are; `other` must be a `dict` |
| `dd \|= other` | O(m) amortized | O(m) amortized | The inherited `dict` update; takes any mapping or iterable of pairs |
| `defaultdict.fromkeys(iterable, value=None)` | O(m) | O(m) | Inherited; the result's `default_factory` is `None` |
| `pickle.dumps(dd)` | O(n) | O(n) | Keys and values priced as for a `dict`; the factory has to be picklable too, and a lambda is not |

### Inherited from dict

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `dd.get(key, default=None)`, `key in dd` | O(1) | O(1) | Never call the factory and never insert |
| `dd.setdefault(key, default=None)`, `dd.pop(key[, default])` | O(1) amortized | O(1) amortized | Use their own default, never the factory |
| `dd[key] = value`, `del dd[key]` | O(1) amortized | O(1) amortized | |
| `len(dd)`, `dd.keys()`, `dd.values()`, `dd.items()` | O(1) | O(1) | Views are live; iterating one is O(n) |
| `dd == other` | O(n) | O(1) | Compares items only: the factory is ignored, and a `defaultdict` equals a `dict` with the same items |

The other `dict` methods are inherited unchanged and cost what they cost on a
[dict](../builtins/dict.md).

## Reading a Missing Key Inserts It

`dd[key]` fills in a missing key even when the code only meant to look. `get()` and `in` look
without inserting.

```python
from collections import defaultdict

groups = defaultdict(list)  # O(1)
groups['a'].append(1)       # O(1 + f) - missing: list() runs and [] is stored
groups['a'].append(2)       # O(1) - present: the factory is not called
assert groups == {'a': [1, 2]}

assert groups.get('b') is None  # O(1) - no insert
assert 'b' not in groups        # O(1) - no insert
assert groups['b'] == []        # O(1 + f) - and now it is there
assert len(groups) == 2
```

## Default Factories

The factory is any zero-argument callable, called once per miss and never for a present key.
`default_factory` can be reassigned at any time; `None` turns a miss back into `KeyError`.

```python
from collections import defaultdict

counts = defaultdict(int)  # int() -> 0
counts['x'] += 1           # O(1 + f) - a read that stores 0, then a store of 1
assert counts == {'x': 1}

members = defaultdict(set)  # set() -> set()
members['team'].add('alice')
assert members['team'] == {'alice'}

nested = defaultdict(lambda: defaultdict(int))  # each miss builds an inner defaultdict
nested['2024']['jan'] += 5
assert nested['2024']['jan'] == 5

counts.default_factory = None  # O(1) - misses raise again
try:
    counts['missing']
except KeyError as error:
    assert error.args == ('missing',)
else:
    raise AssertionError('a missing key was filled in without a factory')
assert counts == {'x': 1}
```

## Copying, Merging and Pickling

`copy()` and `|` build a new `defaultdict` that keeps the factory. `fromkeys()` is the inherited
class method, so its result has no factory. Pickling stores the factory along with the items, and
a lambda cannot be pickled.

```python
import pickle
from collections import defaultdict

original = defaultdict(list, a=[1])  # O(m)
copied = original.copy()             # O(n), shallow
assert copied.default_factory is list
assert copied['a'] is original['a']  # the values are shared, not copied

merged = original | {'b': [2]}  # O(n + m)
assert type(merged) is defaultdict and merged.default_factory is list
reflected = {'b': [2]} | original  # O(n + m), still a defaultdict
assert type(reflected) is defaultdict and list(reflected) == ['b', 'a']

original |= [('c', [3])]  # O(m), in place
assert list(original) == ['a', 'c']

keys = defaultdict.fromkeys('xy', 0)  # O(m)
assert keys.default_factory is None

restored = pickle.loads(pickle.dumps(original))  # O(n)
assert restored == original and restored.default_factory is list

try:
    pickle.dumps(defaultdict(lambda: 0))
except (pickle.PicklingError, AttributeError):
    pass
else:
    raise AssertionError('a lambda factory was pickled')
```

## Common Patterns

### Grouping

```python
from collections import defaultdict

edges = [('a', 'b'), ('b', 'c'), ('a', 'c')]

graph = defaultdict(list)
for u, v in edges:
    graph[u].append(v)  # O(1) amortized per edge
assert graph == {'a': ['b', 'c'], 'b': ['c']}

assert graph.get('c', []) == []  # O(1) - looks without adding 'c'
assert 'c' not in graph
```

### Counting

```python
from collections import Counter, defaultdict

words = ['apple', 'banana', 'apple', 'cherry', 'banana', 'apple']

counts = defaultdict(int)
for word in words:
    counts[word] += 1  # O(1) amortized per word
assert counts == {'apple': 3, 'banana': 2, 'cherry': 1}

# Counter builds the same mapping and adds most_common() and multiset arithmetic
assert Counter(words) == counts
```

## Performance Best Practices

✅ **Do**:

- Look with `in` or `get()` when you do not want the key added; `dd[key]` inserts what it misses
- Set `default_factory = None` once the mapping is built, so a later miss raises instead of growing it
- Use a class such as `int` or `list`, or a module-level function, as the factory if the mapping will be pickled

❌ **Avoid**:

- Reading `dd[key]` for keys that may be absent just to check them: every miss stores an entry
- An expensive factory; every miss pays `f`
- `defaultdict.fromkeys()` when you want a factory; the result has none

## Version Notes

- **All Python 3**: `dd[key]` calls the factory on a miss; `get()`, `in`, `setdefault()` and `pop()` do not

## Related Modules

- **[dict](../builtins/dict.md)** - the base type, and the cost of every inherited operation
- **[Counter](counter.md)** - a `dict` subclass for counting, with `most_common()` and multiset arithmetic
- **[OrderedDict](ordereddict.md)** - the other `dict` subclass in `collections`, for reordering
- **[collections](collections.md)** - the module `defaultdict` belongs to
