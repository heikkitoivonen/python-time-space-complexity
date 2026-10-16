# id() Function Complexity

The `id()` function returns an integer representing an object's identity. In
CPython, this is the object's memory address. The identity is guaranteed to be
unique and constant for an object during its lifetime.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `id(obj)` | O(1) | O(1) | Returns object identity as an integer; memory address in CPython |

## Object Identity and Lifetime

Object identities are guaranteed to be unique only among **simultaneously
existing** objects.

### Coexisting Objects

When two objects exist at the same time, their IDs are guaranteed to differ
unless they are the same object.

```python
# O(1) - distinct objects existing concurrently have distinct IDs
a = [1, 2, 3]
b = [1, 2, 3]
assert id(a) != id(b)  # different objects in memory

# O(1) - aliases share the same identity
c = a
assert id(a) == id(c)  # same object
```

### Address Recycling Across Non-Overlapping Lifetimes

When an object is deallocated, its memory address may be immediately reused by
a newly allocated object. Consequently, comparing IDs of objects with
non-overlapping lifetimes can produce identical values for distinct objects.

```python
# O(1) - the first list is destroyed before the second is created, so CPython
# may hand its address to the second: this is often True
recycled = id([]) == id([])

# O(1) - both lists exist concurrently, so their identities differ
x, y = [], []
assert id(x) != id(y)  # non-overlapping lifetimes are required for reuse
```

### Singletons and Cached Values

CPython caches small integers (-5 to 256; -5 to 1024 from 3.15), interned strings, and built-in
singletons like `None`, `True`, and `False`. References to these values share
the same object identity.

```python
# O(1) - small integers built at runtime come from the cache
small_a, small_b = int("42"), int("42")
assert id(small_a) == id(small_b)  # same cached int object

# Larger integers are fresh objects, so their IDs differ
big_a, big_b = int("2000"), int("2000")
assert id(big_a) != id(big_b)

# O(1) - None is a singleton
assert id(None) == id(None)
```

## Identity Testing: `is` Operator vs `id()`

To test whether two references point to the same object, use the `is` operator
instead of comparing `id()` results.

```python
a = [1, 2, 3]
b = a
c = [1, 2, 3]

# is operator: direct pointer comparison - O(1) time, 0 extra bytes
assert a is b
assert a is not c

# id() comparison: calls id() twice, allocates integers, and runs int.__eq__ - O(1)
assert id(a) == id(b)
```

The `is` operator has two key advantages:

1. **Efficiency**: `a is b` compares pointers directly at the bytecode level without function call overhead or integer object allocation.
2. **Safety**: `is` requires both objects to exist concurrently. Unlike `id(a) == id(b)`, `is` can never return `True` for distinct objects through address recycling (`[] is []` is always `False`).

## Common Use Cases

### Cycle Detection in Traversals

When traversing recursive or cyclic data structures, `id()` can track visited
nodes. Using `id(obj)` in a visited set avoids `TypeError: unhashable type` on
mutable containers (`dict`, `list`, `set`) and avoids triggering recursive
equality checks.

A cycle exists when an edge leads back to an active ancestor. Completed nodes
can be shared without forming a cycle and need not be traversed again. This
example follows dictionary values and list, tuple, and set elements. The root
keeps reachable nodes alive; the containers must remain unchanged during traversal.
Each level the traversal descends adds a Python frame, so following a chain
nested more deeply than `sys.getrecursionlimit()` raises `RecursionError`.

```python
# O(V + E) time, O(V) space to detect reference cycles across V nodes and E edges
def has_cycle(obj):
    active = set()
    completed = set()

    def visit(node):
        node_id = id(node)  # O(1)
        if node_id in active:
            return True
        if node_id in completed:
            return False
        active.add(node_id)  # O(1) average
        if isinstance(node, dict):
            children = node.values()
        elif isinstance(node, (list, tuple, set)):
            children = node
        else:
            children = ()
        for child in children:
            if visit(child):
                return True
        active.remove(node_id)
        completed.add(node_id)
        return False

    return visit(obj)

# Self-referential structure
node = {}
node["child"] = node
assert has_cycle(node)  # cycle detected

# Acyclic structure
tree = {"left": [1, 2], "right": [3, 4]}
assert not has_cycle(tree)

# Shared references are not cycles
shared = [1, 1]
assert not has_cycle([shared, shared])
```

### Identity Caching and Weak References

Using `id(obj)` as a dictionary key to associate metadata with an object is an
anti-pattern if `obj` is not held alive. Once `obj` is garbage collected, a
subsequent object allocated at the same address will collide with the stale key.

```python
# O(1) - storing raw IDs without keeping the referenced object alive can collide
cache = {}
cache[id(list(range(10)))] = "metadata"  # Object immediately freed; key may collide

# O(1) - weakref.WeakKeyDictionary removes entries when keys are garbage collected
import weakref

class Tracked:
    pass

registry = weakref.WeakKeyDictionary()
item = Tracked()
registry[item] = "metadata"
assert registry[item] == "metadata"
```

`WeakKeyDictionary` uses keys' hashing and equality, not identity. For per-object
metadata, use weak-referenceable keys with identity-based equality and hashing,
as in `Tracked` above. Distinct equal keys share an entry; that entry disappears
when the originally inserted key is collected, even if another equal key remains alive.

## Performance Best Practices

✅ **Do**:

- Use the `is` operator (`x is None`, `x is y`) for identity checks.
- Use `id()` when hashing unhashable objects during active graph traversals where objects remain alive.
- Use `weakref.WeakKeyDictionary` for per-object metadata only with weak-referenceable keys that use identity-based equality and hashing.

❌ **Avoid**:

- Comparing `id(a) == id(b)` when `a is b` is intended.
- Using `id(obj)` as a dictionary key without ensuring `obj` stays alive.
- Persisting `id()` values across processes or Python sessions.

## Version Notes

- **Python 3.15+**: The small-integer cache covers -5 to 1024 instead of -5 to 256, so
  runtime-built integers from 257 to 1024 share identity.

## Related Functions

- **[hash()](hash.md)** - Returns an object's hash value for dictionary and set lookups.
- **[isinstance()](isinstance.md)** - Type checking against a class or tuple of classes.
- **[type()](type_func.md)** - Retrieves the runtime type of an object.
