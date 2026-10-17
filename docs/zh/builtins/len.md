---
source_sha: 0aa31d8e74b3cf287660536daef3aa50acfed3e07167aeb3888371da0ed5c807
translated: machine
---

# len() 函数的复杂度

`len(obj)` 返回容器中元素的数量。每个内置容器都把元素个数保存在对象中，因此 `len()` 直接读取该值而无需计数，与容器大小无关。对于其他对象，`len()` 调用其类定义的 `__len__` 方法，开销就是该方法的开销。

内置类型的各行与容器大小无关。`f` 是类自己定义的方法（`__len__`、`__bool__` 或 `__length_hint__`）所花的时间，叠加在 O(1) 的调用之上；该方法分配的内存叠加在 O(1) 的空间之上。对于 `ChainMap`，`m` 是其映射的数量，`t` 是所有映射的键数之和（包括重复的键），`u` 是其中互不相同的键的数量。

## 复杂度参考

### 内置类型

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `len(lst)`, `len(tpl)` | O(1) | O(1) | `list` 和 `tuple` |
| `len(s)` | O(1) | O(1) | `str`：计算字符（码位）数，而不是编码后的字节数 |
| `len(b)`, `len(ba)` | O(1) | O(1) | `bytes` 和 `bytearray`：计算字节数 |
| `len(mv)` | O(1) | O(1) | 至少有一维的 `memoryview`：第一维的长度，而不是元素总数 |
| `len(d)`, `len(d.keys())`, `len(d.values())`, `len(d.items())` | O(1) | O(1) | `dict` 及其视图 |
| `len(fd)` | O(1) | O(1) | `frozendict`，Python 3.15+ |
| `len(st)`, `len(fs)` | O(1) | O(1) | `set` 和 `frozenset` |
| `len(r)` | O(1) | O(1) | `range`：长度在创建 range 时计算一次；超过 `sys.maxsize` 时抛出 `OverflowError` |

### 标准库容器

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `len(dq)` | O(1) | O(1) | `collections.deque` |
| `len(dd)`, `len(od)`, `len(c)` | O(1) | O(1) | `defaultdict`、`OrderedDict` 和 `Counter` 都是 `dict` 的子类 |
| `len(cm)` | O(m + t) | O(m + u) | `collections.ChainMap` 每次调用都会用所有映射中的所有键构建一个集合 |

### 其他对象

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `len(obj)` | O(f) | O(1) | 调用 `type(obj).__len__`；名为 `__len__` 的实例属性会被忽略。结果必须是 0 到 `sys.maxsize` 之间的整数（`int`，或带有 `__index__` 的对象） |
| `len(gen)`, `len(iterator)` | O(1) | O(1) | 生成器以及没有 `__len__` 的迭代器没有长度：抛出 `TypeError` |
| `bool(obj)`, `if obj:` | O(1) 或 O(f) | O(1) | 对内置容器为 O(1)；定义了 `__len__` 而没有 `__bool__` 的类，在 `__len__` 返回非零值时为真 |
| `operator.length_hint(obj, default=0)` | O(1) 或 O(f) | O(1) | 有长度时返回 `len(obj)`，否则返回 `obj.__length_hint__()`，再否则返回 `default`；从不迭代 `obj` 本身 |

## 内置容器

`len()` 对 3 个元素的容器和对 100 万个元素的容器开销相同。对 `str` 它计算字符数，因此可能与编码后 `bytes` 的长度不同。

```python
items = list(range(1_000_000))
assert len(items) == 1_000_000  # O(1)
assert len((1, 2, 3)) == 3  # O(1)

d = {"a": 1, "b": 2}
assert len(d) == len(d.keys()) == len(d.items()) == 2  # O(1)
assert len({1, 2, 2, 3}) == 3  # O(1)

s = "café"
assert len(s) == 4  # O(1) - characters
assert len(s.encode("utf-8")) == 5  # O(1) - bytes, after an O(n) encode

grid = memoryview(bytes(12)).cast("B", shape=[3, 4])
assert len(grid) == 3  # O(1) - the first dimension
assert grid.nbytes == 12
```

## range 对象

range 在创建时根据 `start`、`stop` 和 `step` 计算长度，`len()` 返回保存的值。range 可以比 `sys.maxsize` 更长，但 `len()` 必须返回索引大小的整数，因此对这样的 range 会抛出 `OverflowError`。索引和 `in` 仍然可用。

```python
import sys

r = range(0, 10**9, 3)
assert len(r) == 333_333_334  # O(1)

huge = range(10**20)
try:
    len(huge)
except OverflowError as error:
    assert "too large" in str(error)
else:
    raise AssertionError("expected OverflowError")

assert 10**20 > sys.maxsize
assert huge[-1] == 10**20 - 1  # O(1)
assert 10**19 in huge  # O(1)
```

## 定义了 __len__ 的类

`len(obj)` 调用对象所属类的 `__len__`，因此开销由该方法决定。维护计数或委托给内置容器的方法是 O(1)；通过迭代计数的方法每次调用都是 O(n)。`len()` 会检查结果：负值抛出 `ValueError`，不是整数的值抛出 `TypeError`。

```python
class Stored:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return len(self.items)  # O(1) - delegates to the list


class Counted:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return sum(1 for _ in self.items)  # O(n) - walks every item on each call


assert len(Stored(range(5))) == len(Counted(range(5))) == 5


class Negative:
    def __len__(self):
        return -1


try:
    len(Negative())
except ValueError as error:
    assert ">= 0" in str(error)
else:
    raise AssertionError("expected ValueError")
```

当类没有定义 `__bool__` 时，真值测试也会使用 `__len__`，因此 `if obj:` 的开销与 `len(obj)` 相同。

```python
class Box:
    calls = 0

    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        Box.calls += 1
        return len(self.items)


assert not Box([])  # calls __len__
assert Box([1])
assert Box.calls == 2
```

## 迭代器与生成器

生成器和任何没有 `__len__` 的迭代器一样，不知道自己会产生多少个元素，因此 `len()` 抛出 `TypeError`。计数会消耗这些元素，耗时 O(n)。`operator.length_hint()` 在不迭代的情况下询问：对内置容器的迭代器，它给出剩余元素的确切数量；对生成器，它给出 `default`。

```python
import operator

gen = (x * x for x in range(5))
try:
    len(gen)
except TypeError as error:
    assert "has no len()" in str(error)
else:
    raise AssertionError("expected TypeError")

assert operator.length_hint(gen, -1) == -1  # O(1) - a generator gives no hint
assert sum(1 for _ in gen) == 5  # O(n) - and the generator is now exhausted
assert list(gen) == []

it = iter([10, 20, 30])
next(it)
assert operator.length_hint(it) == 2  # O(1)
assert list(it) == [20, 30]  # nothing was consumed
```

## ChainMap

`ChainMap` 不保存元素个数。每次调用 `len()` 都会用所有映射的键构建一个集合，因此开销与每个映射及其中的每个键成正比，出现在多个映射中的键只计一次。

```python
from collections import ChainMap

defaults = {"color": "red", "size": 10}
overrides = {"color": "blue"}
settings = ChainMap(overrides, defaults)

assert len(settings) == 2  # O(m + t) - "color" is in both maps
```

## 性能最佳实践

✅ **建议**：

- 对内置容器可以随意调用 `len()`，包括在循环条件中；它是 O(1)
- 用 `if container:` 判断是否为空；对内置容器它是 O(1)
- 在自定义容器中维护计数，或委托给内置容器，使 `__len__` 为 O(1)
- 用 `operator.length_hint()` 根据内置容器的迭代器确定缓冲区大小，而不消耗它

❌ **避免**：

- 仅为计数而使用 `len(list(iterator))`：它会构建 O(n) 的列表；`sum(1 for _ in iterator)`
  以 O(1) 空间计数，但两种方式都会消耗迭代器
- 通过迭代实现的 `__len__`；当类没有 `__bool__` 时，`if obj:` 也会调用它
- 在循环中对 `ChainMap` 调用 `len()`：每次调用都会遍历每个映射

## 版本说明

- **Python 3.15+**：对 `frozendict` 调用 `len()` 为 O(1)

## 相关函数

- **[bool()](bool_func.md)** - 真值测试会回退到 `__len__`
- **[iter()](iter.md)** - 生成器和大多数迭代器没有长度
- **[range](range.md)** - range 在创建时计算长度
- **[sum()](sum.md)** - 统计迭代器中的元素个数
- **[collections](../stdlib/collections.md)** - `deque`、`Counter` 和 `ChainMap`
- **[operator](../stdlib/operator.md)** - 用于迭代器的 `length_hint()`
