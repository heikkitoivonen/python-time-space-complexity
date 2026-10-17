# super() Function Complexity

The `super()` function returns a proxy that looks attributes up in an object's method resolution
order (MRO), starting after a given class. It is how a method reaches the next implementation in a
hierarchy, which in multiple inheritance may be a sibling class rather than a parent.

A lookup through `super()` is not cached. Ordinary attribute access, `obj.name` or `Parent.method`,
goes through a per-class cache and costs O(1) once cached, however deep the hierarchy, but every
`super().name` scans the MRO tuple from the front: first to find the starting class, then through
each later class's `__dict__` until one defines the name.

`d` is the classes in the MRO the lookup uses: `type(obj).__mro__`, or `obj.__mro__` when `obj` is a
class. Positions in it count from 1. `s` is the position of the starting class, the class `super()`
was called in or the one passed as its first argument. `p` is the position where the lookup stops:
the class that defines the name, or `d` when none does; `s <= p <= d`. Name hashing is treated as
O(1), and a found descriptor's `__get__` and the method that is then called cost what they do.

## Complexity Reference

### Creating a super object

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `super()` inside a method | O(s) | O(1) | Uses the function's `__class__` cell and its first argument, then checks the argument's MRO for that class |
| `super(cls, obj)` | O(s) | O(1) | `obj` is an instance of `cls` or a subclass of it; any other object except `None` raises `TypeError` |
| `super(cls)`, `super(cls, None)` | O(1) | O(1) | Unbound: holds no object, so looking up a method of `cls`'s bases raises `AttributeError` |
| `super()` in a function with no arguments, or outside a class body | O(1) | O(1) | Raises `RuntimeError`, as in a `staticmethod` that takes no arguments |

### Attribute lookup

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `super().name`, `super(cls, obj).name` | O(p) | O(1) | Not cached: scans the MRO to the starting class, then each later class's `__dict__` until one defines `name`, and binds what it finds with `__get__` |
| `super().name`, `name` not defined after the starting class | O(d) | O(1) | Scans to the end of the MRO, then the `super` object's own attributes such as `__self__`; anything else raises `AttributeError` |
| `super().name = value`, `del super().name` | O(s) | O(1) | Creating the `super` object, then `AttributeError`: it cannot assign or delete through the MRO |
| `Parent.method(self)` | O(1) | O(1) | An ordinary class attribute, cached per class; it names one class and does not follow the instance's MRO |

## Calling the Next Method

### Single Inheritance

In a single chain, `super()` reaches the parent's version of the method.

```python
class Parent:
    def __init__(self, name):
        self.name = name

class Child(Parent):
    def __init__(self, name, age):
        super().__init__(name)  # O(p) - Parent is next in Child's MRO
        self.age = age

child = Child("Alice", 30)
assert (child.name, child.age) == ("Alice", 30)
assert Child.__mro__ == (Child, Parent, object)
```

### The Instance's MRO Decides What Is Next

`super()` follows the MRO of the object, not the bases written in the class. In a diamond, `B`'s
`super()` reaches its sibling `C` when the object is a `D`, so `A` runs once.

```python
calls = []

class A:
    def setup(self):
        calls.append("A")

class B(A):
    def setup(self):
        calls.append("B")
        super().setup()

class C(A):
    def setup(self):
        calls.append("C")
        super().setup()

class D(B, C):
    def setup(self):
        calls.append("D")
        super().setup()

D().setup()
assert calls == ["D", "B", "C", "A"]
assert D.__mro__ == (D, B, C, A, object)

calls.clear()
B().setup()  # On a B, the next class after B is A
assert calls == ["B", "A"]
```

### Explicit Arguments

`super()` with no arguments is `super(__class__, first_argument)`. The two-argument form names
them itself, and in a `classmethod` the first argument is the class.

```python
class Parent:
    def method(self):
        return "parent"

    @classmethod
    def create(cls):
        return cls()

class Child(Parent):
    def method(self):
        assert super().method() == super(Child, self).method()
        return "child"

    @classmethod
    def create(cls):
        instance = super().create()  # super(Child, cls)
        instance.created = True
        return instance

child = Child.create()
assert type(child) is Child and child.created
assert child.method() == "child"
```

## Lookup Cost

### Lookups Are Not Cached

Every `super().name` scans the MRO again, so its cost is the position of the class that defines the
name. When the starting class is near the front of the MRO, a method found in the next class is
cheap however long the MRO is. One defined near the far end costs the length of the walk on every
call, while naming the class directly is an O(1) cached lookup that skips cooperative dispatch.

```python
class Root:
    def ping(self):
        return "root"

cls = Root
for i in range(200):
    cls = type(f"Level{i}", (cls,), {})

class Leaf(cls):
    def ping(self):
        return super().ping()  # O(p) - Root is at position 202 of 203

    def direct(self):
        return Root.ping(self)  # O(1) - a cached class attribute

leaf = Leaf()
assert len(Leaf.__mro__) == 203
assert leaf.ping() == leaf.direct() == "root"
```

### A Missing Name Scans the Whole MRO

When no class after the starting one defines the name, the lookup reaches the end of the MRO
before it raises.

```python
class Base:
    pass

class Child(Base):
    def probe(self):
        try:
            super().missing  # O(d) - checks every later class
        except AttributeError as error:
            return str(error)
        raise AssertionError("expected AttributeError")

assert "missing" in Child().probe()
```

## Edge Cases

### Where Zero-Argument super() Works

The zero-argument form needs the function's first argument and the `__class__` cell the compiler
creates for functions defined in a class body that use `super`. A `staticmethod` with no arguments
has neither argument nor object, and a function defined outside a class has no cell.

```python
class Example:
    @staticmethod
    def static():
        return super().anything

try:
    Example.static()
except RuntimeError as error:
    assert "no arguments" in str(error)
else:
    raise AssertionError("expected RuntimeError")

def outside(self):
    return super()

try:
    outside(Example())
except RuntimeError as error:
    assert "__class__ cell not found" in str(error)
else:
    raise AssertionError("expected RuntimeError")
```

### Properties Through super()

Reading a parent's property through `super()` runs its getter. Assigning through `super()` raises,
so a subclass setter reaches the parent's through the property object.

```python
class Parent:
    def __init__(self):
        self._value = 0

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new):
        self._value = new

class Child(Parent):
    @property
    def value(self):
        return super().value  # Runs Parent's getter

    @value.setter
    def value(self, new):
        if new < 0:
            raise ValueError("must be non-negative")
        Parent.value.fset(self, new)  # super().value = new would raise

    def assign_through_super(self, new):
        super().value = new

child = Child()
child.value = 10
assert child.value == 10

try:
    child.assign_through_super(5)
except AttributeError:
    pass
else:
    raise AssertionError("expected AttributeError")
assert child.value == 10
```

## Common Patterns

### Cooperative Initialisation

Each class takes the keyword arguments it knows and passes the rest along, so every `__init__` in
the MRO runs exactly once whatever order the classes are combined in.

```python
class Named:
    def __init__(self, *, name, **rest):
        super().__init__(**rest)
        self.name = name

class Sized:
    def __init__(self, *, size, **rest):
        super().__init__(**rest)
        self.size = size

class Item(Named, Sized):
    pass

item = Item(name="box", size=3)
assert (item.name, item.size) == ("box", 3)
assert Item.__mro__ == (Item, Named, Sized, object)
```

## Performance Best Practices

✅ **Do**:

- Call `super()` in every method of a cooperative hierarchy, so each class runs once in MRO order
- Pass unrecognised keyword arguments on with `**rest`, so classes combine in any order
- Name the class directly, `Parent.method(self)`, where a call in a hot path over a deep hierarchy
  does not need cooperative dispatch: it is O(1) where `super()` is O(p)

❌ **Avoid**:

- Mixing `super()` with explicit `Parent.method(self)` calls in a diamond; a class can run twice
  or be skipped
- Zero-argument `super()` in a function with no arguments, or one defined outside a class; it
  raises `RuntimeError`
- Assigning through `super()`; it raises `AttributeError`

## Related Functions

- **[classmethod()](classmethod.md)** - Methods whose `super()` binds to the class
- **[staticmethod()](staticmethod.md)** - Methods that receive no instance or class for `super()` to bind
- **[property()](property.md)** - Descriptors a subclass can extend through `super()`
- **[type()](type_func.md)** - Creates classes, and with them their MRO
- **[issubclass()](issubclass.md)** - The MRO scan `super(cls, obj)` also performs
