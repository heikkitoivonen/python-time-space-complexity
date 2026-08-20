---
source_sha: d121e0a8af5ee71633a5877aead4146b5a677a147d64343c227a3ee27348715b
translated: machine
---

# len() 函数的复杂度

`len()` 函数返回容器对象中元素的数量。

## 按类型划分的复杂度

| 类型 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| `list` | O(1) | O(1) | 直接读取长度属性 |
| `tuple` | O(1) | O(1) | 不可变，已缓存 |
| `dict` | O(1) | O(1) | 自身维护大小 |
| `set` | O(1) | O(1) | 自身维护大小 |
| `str` | O(1) | O(1) | 不可变，已缓存 |
| `bytes` | O(1) | O(1) | 不可变，已缓存 |
| `range` | O(1) | O(1) | 计算得出，并不存储 |
| `deque` | O(1) | O(1) | 自身维护大小 |
| `defaultdict` | O(1) | O(1) | 继承自字典 |
| `OrderedDict` | O(1) | O(1) | 自身维护大小 |

## 内置容器类型

所有内置容器类型都会缓存自身长度，并以常数时间返回：

```python
# All O(1)
lst = [1, 2, 3, 4, 5]
length = len(lst)  # O(1) - stored length

tpl = (1, 2, 3)
length = len(tpl)  # O(1) - immutable

dct = {'a': 1, 'b': 2}
length = len(dct)  # O(1) - maintains size

s = "hello"
length = len(s)    # O(1) - immutable string
```

## 自定义对象

对于自定义类，`len()` 会调用 `__len__()` 方法：

```python
class MyContainer:
    def __init__(self, items):
        self.items = items
    
    def __len__(self):
        # Your implementation determines complexity
        return len(self.items)  # O(1) if efficient

# Usage
obj = MyContainer([1, 2, 3])
length = len(obj)  # O(1) - delegates to cached length

# Inefficient implementation
class BadContainer:
    def __init__(self, items):
        self.items = items
    
    def __len__(self):
        # Recomputes from scratch - O(n)!
        return sum(1 for _ in self.items)

obj = BadContainer([1, 2, 3])
length = len(obj)  # O(n) - iterates through items
```

## 生成器表达式与迭代器

`len()` 对生成器和迭代器**不适用**：

```python
# Works - list has cached length
lst = [1, 2, 3, 4, 5]
length = len(lst)  # O(1)

# Fails - generators don't have length
gen = (x for x in range(5))
# length = len(gen)  # TypeError: object of type 'generator' has no len()

# Must consume iterator to count
count = sum(1 for x in gen)  # O(n) - must iterate
```

## 常见用法

### 判断容器是否为空

```python
# Correct - O(1), doesn't create list
if len(container) > 0:
    process(container)

# Also correct - O(1), more Pythonic
if container:
    process(container)

# Inefficient - creates a list
if len(list(generator)) > 0:  # O(n) - forces evaluation
    process(generator)
```

### 大小校验

```python
def process_list(items):
    if len(items) == 0:      # O(1)
        raise ValueError("Empty list")
    if len(items) > 1000:    # O(1)
        raise ValueError("Too large")
    
    # Process items
    for item in items:
        pass
```

### 比较容器大小

```python
# All O(1)
if len(list1) > len(list2):
    smaller = list2
    larger = list1
else:
    smaller = list1
    larger = list2

# More efficient than computing actual difference
if len(list1) != len(list2):
    print("Different sizes")
```

## 性能说明

### 循环中的长度操作

```python
# O(n) - good, length is O(1)
for i in range(len(items)):
    process(items[i])

# Also O(n) - length check is O(1) per iteration
count = 0
while count < len(items):
    process(items[count])
    count += 1
```

### 预先计算长度

```python
items = get_large_list()

# Don't do this - wastes a variable
length = len(items)
for i in range(length):  # length already O(1)
    process(items[i])

# Instead - directly use len() which is O(1)
for i in range(len(items)):
    process(items[i])
```

## 特殊情况

### range 对象

```python
# Range length is O(1), not O(n)
r = range(10**1000)
length = len(r)  # O(1) - computed from start, stop, step

# This is computed, not stored
# So even huge ranges have O(1) length
```

### 字符串编码

```python
# All string types have O(1) length
s = "hello"
length = len(s)  # O(1) - character count

b = b"hello"
length = len(b)  # O(1) - byte count

# Note: len(str) counts characters, not bytes
s = "café"
print(len(s))      # 4 - four characters
print(len(s.encode('utf-8')))  # 5 - five bytes
```

## 版本说明

- **Python 2.x**：`len()` 适用于内置类型以及自定义的 `__len__` 方法
- **Python 3.x**：行为相同，但更加一致
- **所有版本**：内置容器为 O(1)（它们会缓存长度）

## 相关函数

- **[all()](all.md)** - 检查是否所有元素都为真
- **[any()](any.md)** - 检查是否存在为真的元素
- **[max()](max.md)** - 求最大值
- **[min()](min.md)** - 求最小值
- **[sum()](sum.md)** - 求所有元素之和

## 最佳实践

✅ **推荐**：

- 用 `len()` 判断容器是否为空（它是 O(1)）
- 用 `if container:` 做真值判断
- 仅在紧凑循环中多次使用时才缓存长度

❌ **避免**：

- 用 `len(list(generator))` 统计生成器元素数量（O(n)）
- 在 `__len__` 中重新计算长度（应当缓存）
- 想当然认为生成器有长度（并没有）
