---
source_sha: f5c4b3c5bd9a612e361874983042cd25d27aa989a7e7b47532e46516d57e6430
translated: machine
---

# collections 模块的复杂度

`collections` 模块提供了对 `dict`、`list`、`str` 和 `tuple` 进行特化的容器类型。其中五个
有自己的页面（链接见下文），`collections.abc` 中的抽象基类也有自己的页面。本页其余部分
介绍 `ChainMap`——它按顺序搜索一个映射列表而不是合并它们——以及 `UserDict`、`UserList`
和 `UserString`，它们把一个普通的 `dict`、`list` 或 `str` 保存在 `data` 属性中，并把每个
操作转发给它。

## deque

操作、复杂度和示例请参阅 [deque](deque.md)。

## defaultdict

操作、复杂度和示例请参阅 [defaultdict](defaultdict.md)。

## Counter

操作、复杂度和示例请参阅 [Counter](counter.md)。

## namedtuple

操作、复杂度和示例请参阅 [namedtuple](namedtuple.md)。

## OrderedDict

操作、复杂度和示例请参阅 [OrderedDict](ordereddict.md)。

## collections.abc

抽象基类及其混入方法的开销请参阅 [collections.abc](collections.abc.md)。`ChainMap` 和这些包装器
自身没有定义的一切都来自这些混入，而混入是用包装器自己的 `__getitem__`、`__iter__` 和
`__setitem__` 写成的，因此重写了其中之一的子类会在混入的每一步为此付出代价。

## 规模变量

对于 `ChainMap`，`n` 是映射的数量，`i` 是第一个持有该键的映射的位置（未命中时为 `n`），
`N` 是所有映射中条目的总数，`m` 是 `maps[0]` 中的条目数。对于包装器，`n` 是 `len(wrapper)`，
`d` 是之前的删除在字典表中留下的槽位数。在所有地方，`k` 是另一个操作数的大小或提供的项目数。
键的哈希和比较视为 O(1)，`ChainMap` 的各行假定其映射都是字典，转发给 `data` 的操作的开销以
[dict](../builtins/dict.md)、[list](../builtins/list.md) 或 [str](../builtins/str.md) 页面
所述为准。

## 复杂度参考

### ChainMap

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `collections.ChainMap(*maps)` | O(n) | O(n) | 把映射保存在一个列表中；不复制也不合并任何内容，因此之后对任一映射的修改都会直接体现 |
| `ChainMap.maps` | O(1) | O(1) | 列表本身；重新排序或扩展它即可改变搜索顺序 |
| `cm[key]` | O(i) | O(1) | 按顺序尝试每个映射，直到某个映射含有该键；未命中会尝试全部 n 个并抛出 `KeyError` |
| `key in cm` | O(i) | O(1) | 同样的搜索 |
| `cm.get(key, default=None)` | O(i) | O(1) | 命中时搜索两次：一次用于 `in`，一次取值 |
| `cm[key] = value`, `del cm[key]`, `cm.pop(key)`, `cm.popitem()` | O(1) | O(1) | 仅作用于 `maps[0]`；删除位于后面映射中的键会抛出 `KeyError` |
| `cm.update(other)`, `cm \|= other` | O(k) | O(k) | 写入 `maps[0]` |
| `cm.setdefault(key, default=None)` | O(i) | O(1) | 返回在任一映射中找到的值；只有未命中才会写入，并且写入 `maps[0]` |
| `cm.clear()` | O(m) | O(1) | 只清空 `maps[0]` |
| `bool(cm)` | O(n) | O(1) | 在第一个非空映射处停止；全是空映射的链会检查每一个 |
| `len(cm)` | O(n + N) | O(n + N) | 构建所有键的集合以统计不重复的键，会访问每个映射，即使它是空的 |
| `cm.keys()`, `cm.items()`, `cm.values()` | O(1) | O(1) | 链上的视图；开销在迭代它们时支付 |
| 迭代 `cm` 或 `cm.keys()` | O(n + N) | O(N) | 在产出第一个键之前先构建所有键的字典：先是最后一个映射的键，然后是每个更前面的映射的新键 |
| 迭代 `cm.items()` 或 `cm.values()`, `dict(cm)` | O(n + N·n) | O(N) | 先遍历键，再对每个键执行 `cm[key]`，这会再次搜索整条链 |
| `cm == other` | O(n + N·n + k) | O(N + k) | 把两边都展平成字典再比较 |
| `cm.new_child(m=None, **kwargs)` | O(n + k) | O(n + k) | 一个共享所有现有映射、并把 `m` 放在最前面的新 `ChainMap`；两者都给出时关键字参数写入 `m`，否则写入一个新字典 |
| `ChainMap.parents` | O(n) | O(n) | 基于 `maps[1:]` 的新 `ChainMap`；映射是共享的，列表不是 |
| `cm.copy()` | O(m + n) | O(m + n) | 复制 `maps[0]`，共享其余部分 |
| `ChainMap.fromkeys(iterable, value=None)` | O(k) | O(k) | 单映射链下的一个字典 |
| `cm \| other` | O(m + n + k) | O(m + n + k) | 先 `copy()`，再把 `other` 写入副本的第一个映射 |
| `other \| cm` | O(n + N + k) | O(N + k) | 一个把所有条目展平保存的单映射 `ChainMap`：层次消失了 |

### UserDict

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `collections.UserDict(dict=None, /, **kwargs)` | O(k) | O(k) | 通过 `update()` 填充 `data`，每个项目一次 `__setitem__` 调用 |
| `UserDict.data` | O(1) | O(1) | 普通字典；直接操作它可以绕过包装器及其混入 |
| `ud[key]`, `ud[key] = value`, `del ud[key]`, `key in ud`, `len(ud)` | O(1) | O(1) | 转发；`ud[key]` 先检查成员关系，以便子类的 `__missing__` 能够运行 |
| `ud.get(key, default=None)` | O(1) | O(1) | Python 3.12+：不调用 `__missing__`；3.12 之前会调用 |
| `ud.keys()`, `ud.items()`, `ud.values()` | O(1) | O(1) | 持有包装器引用的视图 |
| 迭代 `ud` 或 `ud.keys()` | O(n) | O(1) | 字典自身的迭代 |
| 迭代 `ud.items()` 或 `ud.values()` | O(n) | O(1) | 每个键一次 `ud[key]` |
| `ud.update(other)` | O(k) | O(1) | 每个项目一次 `__setitem__` 调用 |
| `ud \|= other` | O(k) | O(1) | 对 `data` 的一次 `dict.update` |
| `ud \| other` | O(n + k) | O(n + k) | 合并两个字典，再用结果构建一个新包装器，因此每个项目会再次经过 `__setitem__` |
| `ud.copy()` | O(n) | O(n) | 普通 `UserDict` 复制 `data`；子类先被浅复制，再通过 `update()` 重新填充 |
| `UserDict.fromkeys(iterable, value=None)` | O(k) | O(k) | 每个键一次 `__setitem__` 调用 |
| `ud.pop(key)`, `ud.setdefault(key, default=None)` | O(1) | O(1) | 先 `ud[key]`，再 `del ud[key]` 或 `ud[key] = default` |
| `ud.popitem()` | O(d) | O(1) | 移除迭代顺序中的第一个键；d 是在它之前被删除的条目数，新的迭代器必须跳过它们 |
| `ud.clear()` | O(n·(n + d)) | O(1) | 反复 `popitem()` 直到为空，每次调用都要跳过之前调用清空的所有槽位；`ud.data.clear()` 是 O(n) |
| `ud == other` | O(n + k) | O(n + k) | 把两边都展平成字典再比较，即使 `other` 已经是字典 |

### UserList

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `collections.UserList(initlist=None)` | O(k) | O(k) | 复制一个列表或另一个 `UserList`；其他任何可迭代对象都会被消费到一个新列表中 |
| `UserList.data` | O(1) | O(1) | 普通列表 |
| `ul[i]`, `ul[i] = value`, `len(ul)` | O(1) | O(1) | 转发 |
| `ul[i:j]` | O(j - i) | O(j - i) | 返回通过其 `__init__` 构建的 `type(ul)`；`copy()`、`+` 和 `*` 也是如此 |
| `ul.append(x)` | O(1) 摊还 | O(1) | 转发 |
| `ul.insert(i, x)`, `del ul[i]`, `ul.pop(i=-1)`, `ul.remove(x)` | O(n) | O(1) | `i` 之后的项目会移动，因此从末尾 `pop()` 是 O(1) |
| `ul.extend(other)`, `ul += other` | O(k) | O(k) | `+=` 在扩展之前会把非列表的可迭代对象复制成列表 |
| `ul + other`, `ul * k` | O(n + k), O(n·k) | O(n + k), O(n·k) | `type(ul)` 的新实例；`other` 可以是列表、`UserList` 或任何可迭代对象 |
| `ul *= k` | O(n·k) | O(n·k) | 原地 |
| `x in ul`, `ul.count(x)`, `ul.index(x)`, `ul.reverse()` | O(n) | O(1) | 转发 |
| `ul.sort(*, key=None, reverse=False)` | O(n log n) | O(n) | 对 `data` 的 `list.sort` |
| `ul.clear()`, `ul.copy()` | O(n) | O(1), O(n) | `copy()` 就是 `type(ul)(ul)` |
| 迭代 `ul` 或 `reversed(ul)` | O(n) | O(1) | `Sequence` 混入：每个项目一次 `ul[i]` 调用，`iter()` 在 `ul[n]` 抛出 `IndexError` 时结束 |
| `ul == other`, `ul < other` | O(min(n, k)) | O(1) | 把 `data` 与另一个列表或另一个 `UserList` 的 `data` 比较 |

### UserString

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `collections.UserString(seq)` | O(1) | O(1) | `str` 原样保存而不复制；其他任何对象都先经过 `str()`，开销取决于该转换 |
| `UserString.data` | O(1) | O(1) | 普通字符串 |
| `us[i]`, `us[i:j]` | O(1), O(j - i) | O(1), O(j - i) | 包裹该字符或切片的新 `type(us)`，绝不会是 `str` |
| 迭代 `us` | O(n) | O(1) | `Sequence` 混入：每个字符一次 `us[i]`，因此每个字符都作为一个新包装器到来 |
| `len(us)`, `str(us)` | O(1) | O(1) | `str(us)` 就是 `data` 本身 |
| `hash(us)` | O(n) | O(1) | `data` 的哈希 |
| `sub in us`, `us.count(sub)`, `us.find(sub)`, `us.rfind(sub)`, `us.index(sub)`, `us.rindex(sub)`, `us.startswith(prefix)`, `us.endswith(suffix)` | O(n + k) 平均 | O(1) | `str` 搜索的平均情况；结果是普通的 `int` 或 `bool` |
| `us.capitalize()`, `us.casefold()`, `us.center(width)`, `us.expandtabs()`, `us.ljust(width)`, `us.lower()`, `us.lstrip()`, `us.removeprefix(prefix)`, `us.removesuffix(suffix)`, `us.replace(old, new)`, `us.rjust(width)`, `us.rstrip()`, `us.strip()`, `us.swapcase()`, `us.title()`, `us.translate(table)`, `us.upper()`, `us.zfill(width)` | O(n + 输出) | O(n + 输出) | 一个与输出等长的新 `str`，用 `type(us)` 包裹：大小写和 strip 类方法为 n，填充类方法为 `width`，替换或转换表则取决于它们产生的内容 |
| `us.split()`, `us.rsplit()`, `us.splitlines()`, `us.partition(sep)`, `us.rpartition(sep)` | O(n) | O(n) | 装着 `str` 的普通 `list` 或 `tuple`：包装器类型被丢弃 |
| `us.join(iterable)` | O(k + 输出) | O(k + 输出) | 普通 `str`；k 为拼接的字符串数，若输入不是序列则先收集到列表中 |
| `us.encode()` | O(n) | O(n) | 普通 `bytes` |
| `us.format(*args, **kwargs)`, `us.format_map(mapping)` | O(n + 输出) | O(n + 输出) | 普通 `str`；整个模板都会被扫描 |
| `us.isalnum()`, `us.isalpha()`, `us.isdecimal()`, `us.isdigit()`, `us.isidentifier()`, `us.islower()`, `us.isnumeric()`, `us.isprintable()`, `us.isspace()`, `us.istitle()`, `us.isupper()` | O(n) | O(1) | 在能决定答案的第一个字符处停止 |
| `us.isascii()` | O(1) | O(1) | 读取 `str` 保存的一个标志 |
| `us + other`, `other + us` | O(n + k) | O(n + k) | 新包装器；非 `str` 操作数会经过 `str()` |
| `us * k`, `us % args` | O(n·k), O(n + 输出) | O(n·k), O(n + 输出) | 新包装器 |
| `us == other`, `us < other` | O(min(n, k)) | O(1) | 比较 `data`；`other` 可以是 `str` 或 `UserString` |
| `UserString.maketrans(x, y=None, z=None)` | O(k) | O(k) | 就是 `str.maketrans` |
| `int(us)` | O(n²) | O(n) | 对 `data` 的 `int()`，因此 [int](../builtins/int.md) 页面上的十进制位数上限适用 |
| `float(us)`, `complex(us)` | O(n) | O(n) | `data` 的转换 |

## 用 ChainMap 分层

### 查找会沿着链走

`ChainMap` 保存的是引用而非副本。每次读取都按顺序尝试各个映射并在第一次命中处停止，因此位于
最后一个映射中的键需要 n 次查找，未命中则总是如此。写入只进入 `maps[0]`，这正是链适合用于
作用域的原因：子作用域遮蔽父作用域而不触碰它们。

```python
from collections import ChainMap

defaults = {"timeout": 30, "retries": 3}
user = {"timeout": 60}
config = ChainMap(user, defaults)  # O(n) - two references, nothing copied

assert config["timeout"] == 60  # O(i) - found in the first map
assert config["retries"] == 3  # O(i) - found in the second
assert config.get("colour", "none") == "none"  # O(n) - a miss checks every map

config["retries"] = 5  # O(1) - into maps[0]
assert user == {"timeout": 60, "retries": 5}
assert defaults["retries"] == 3  # the parent is untouched

del config["timeout"]  # O(1) - maps[0] has it
try:
    del config["timeout"]  # now only defaults has it
except KeyError as error:
    assert "first mapping" in str(error)
else:
    raise AssertionError("a key in a later map was deleted")

# Scopes: new_child() puts a fresh map in front, parents drops the front one
scope = config.new_child()  # O(n) - shares every map
scope["timeout"] = 1
assert scope["timeout"] == 1 and config["timeout"] == 30
assert scope.parents.maps == config.maps  # O(n) - a new list over the same maps
```

### 计数和迭代要为每个键付出开销

`len()` 没有捷径：链会构建所有键的集合来得知有多少不重复的键，而迭代会在产出第一个键之前
构建所有键的字典。两者都会访问每个映射和每个条目，即 O(n + N)，而这个结构本身不保存任何
东西，因此不应在循环中对大映射的链进行计数或迭代。迭代顺序是最后一个映射的键，然后是每个更前面映射中
尚未见过的键。

```python
from collections import ChainMap

first = {"a": 1, "b": 2}
second = {"c": 3, "a": 0}
chain = ChainMap(first, second)

assert len(chain) == 3  # O(n + N) - a set of every key, counted once each
assert list(chain) == ["c", "a", "b"]  # O(n + N) - built before the first key is yielded
assert dict(chain) == {"a": 1, "b": 2, "c": 3}  # O(n + N·n) - each key searched again

# Flattening through | keeps the values the chain would return, but not the layers
flat = {"z": 26} | chain  # O(n + N + k)
assert flat.maps == [{"z": 26, "c": 3, "a": 1, "b": 2}]
```

## 用 UserDict、UserList 和 UserString 包装

### 钩子对每个项目运行一次

这些包装器就是为了被继承而存在的。重写的 `UserDict.__setitem__` 能看到构造、`update()`、
`fromkeys()` 和 `|`，它们都逐项经过它，而继承 `dict` 则不会；`|=` 和转发给 `data` 的方法会绕过它。
在 `UserList` 或 `UserString` 上重写的 `__getitem__` 能看到迭代的每一步，因为迭代是逐个索引地
经过它，而不是使用底层对象的迭代器。

```python
from collections import UserDict, UserList

class Recording(UserDict):
    def __init__(self, *args, **kwargs):
        self.writes = 0
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.writes += 1
        super().__setitem__(key, value)

recorded = Recording({"a": 1, "b": 2, "c": 3})  # O(k) - one __setitem__ per item
assert recorded.writes == 3

recorded.update(d=4)  # O(k) - the mixin loop, one __setitem__ per item
assert recorded.writes == 4

merged = recorded | {"e": 5}  # O(n + k) - the merged dict is fed back through __setitem__
assert merged.writes == 5
assert recorded.writes == 4

class Indexed(UserList):
    reads = 0

    def __getitem__(self, index):
        Indexed.reads += 1
        return super().__getitem__(index)

items = Indexed([10, 20, 30])
assert list(items) == [10, 20, 30]  # O(n) - n + 1 __getitem__ calls, the last raising IndexError
assert Indexed.reads == 4
```

### 清空 UserDict

`UserDict` 没有定义 `clear()`、`popitem()` 或 `pop()`；它们从 `MutableMapping` 继承而来。它的
`popitem()` 取新迭代器产出的第一个键，而字典的迭代器必须跳过之前的删除清空的每个槽位，因此
一次 `popitem()` 的开销是 O(d)，通过 `clear()` 清空整个字典的开销是 O(n·(n + d))。请直接
清空 `data` 字典。

```python
from collections import UserDict

wrapped = UserDict({"a": 1, "b": 2, "c": 3})

assert wrapped.popitem() == ("a", 1)  # O(d) - the first key still present
assert wrapped.popitem() == ("b", 2)

wrapped.data.clear()  # O(n) - the dict's own clear
assert len(wrapped) == 0

wrapped.update(zip("xyz", range(3)))
wrapped.clear()  # O(n·(n + d)) - popitem() until empty
assert len(wrapped) == 0
```

### 包装器返回的仍是包装器

`UserString` 中变换文本的方法，如 `upper()` 和 `strip()`，返回一个新的 `type(us)`，索引和迭代
也是如此，因此对 `UserString` 的循环会为每个字符分配一个包装器。返回文本容器的方法，如 `split()`
和 `partition()`，返回装在普通 `list` 或 `tuple` 中的普通 `str`，而 `join()`、`format()` 和
`format_map()` 返回普通 `str`。`UserList` 的切片和算术
运算同样返回通过 `__init__` 构建的 `type(ul)`，因此带有额外必需参数的子类构造函数会让切片失效。

```python
from collections import UserString

source = "abc"
text = UserString(source)  # O(1) - the str is held, not copied
assert text.data is source

assert type(text.upper()) is UserString  # O(n) - a new str, wrapped
assert type(text[0]) is UserString  # O(1) - even one character is wrapped
assert all(type(char) is UserString for char in text)  # O(n) - one wrapper per character

assert type(text.split()) is list and type(text.split()[0]) is str  # O(n) - plain str inside
assert type(text.join(["x", "y"])) is str  # O(output) - plain str
assert type(text.encode()) is bytes
assert text.count("b") == 1 and text.find("z") == -1  # O(n + k) - plain int results
```

## 常见模式

### 带覆盖的设置

```python
from collections import ChainMap

defaults = {"host": "localhost", "port": 8000, "debug": False}
environment = {"port": 8080}
command_line = {"debug": True}

settings = ChainMap(command_line, environment, defaults)  # O(n) - three references

assert settings["port"] == 8080  # O(i) - the environment wins over the default
assert settings["debug"] is True  # O(i) - the command line wins over everything
assert settings["host"] == "localhost"  # O(n) - found in the last map

# Read the resolved settings once, then work from the dict
resolved = dict(settings)  # O(n + N·n) - once, not on every read
assert resolved == {"host": "localhost", "port": 8080, "debug": True}
```

## 性能最佳实践

✅ **推荐**：

- 保持 `ChainMap` 简短：每次未命中、落到默认值的 `get()`、以及读取最后一个映射中的键，都要为每个映射付出一次查找
- 在循环中读取链时，用 `dict(chain)` 展平一次，让逐映射的搜索每个键只发生一次，而不是每次读取一次
- 通过 `data.clear()` 清空 `UserDict`；继承的 `clear()` 关于条目数及其之前删除的槽位数是平方级的
- 当热循环不需要子类钩子时，直接使用 `ud.data`、`ul.data` 或 `us.data`

❌ **避免**：

- 在循环中对 `ChainMap` 进行 `len()` 或迭代——每次调用都会重建所有键的集合或字典
- 在热路径上用 `==` 比较 `UserDict`：混入每次都把两边展平成新字典
- 逐字符迭代 `UserString`；每个字符都是一个新的包装器对象
- `__init__` 需要额外参数的 `UserList` 子类：切片、`copy()`、`+` 和 `*` 都通过它来构造

## 版本说明

- **Python 3.12+**：`UserDict.get()` 对缺失的键返回默认值而不调用 `__missing__`；3.12 之前，继承的 `Mapping.get()` 经过 `__getitem__` 并会调用它
- **所有 Python 3**：对 `ChainMap` 的 `len()` 和迭代要为每个映射中的每个条目付出开销；链没有任何缓存

## 相关模块

- **[dict](../builtins/dict.md)** - 转发的 `UserDict` 操作的开销
- **[list](../builtins/list.md)** - 转发的 `UserList` 操作的开销
- **[str](../builtins/str.md)** - 转发的 `UserString` 操作的开销
