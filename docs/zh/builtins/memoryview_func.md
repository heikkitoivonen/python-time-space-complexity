---
source_sha: fca17154f0b81909dbd752d49eace2541294a41ebc4b8567097c9ffc01052f91
translated: machine
---

# memoryview() 函数的复杂度

`memoryview()` 函数将一个缓冲区导出者（`bytes`、`bytearray`、`array.array` 以及任何支持缓冲区协议的对象）
包装成视图，就地读写导出者的内存。创建、切片和 cast 视图从不复制数据；把视图转换回 `bytes` 或 `list`
则总是复制。

## 复杂度分析

设 `n` 为视图在所有维度上的元素总数，`k` 为切片覆盖的元素数，`e` 为导出者自身 `hash()` 的成本。
空间不包括导出者的缓冲区，所有视图共享该缓冲区。这些界针对内置导出者，且按数字的情形把元素比较
计为 O(1)；用 Python 编写的 `__buffer__()` 或带有自定义 `__eq__()` 的值的成本取决于其实现。

| 操作 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `memoryview(obj)` | O(1) | O(1) | 视图对象的大小取决于 `ndim`，与缓冲区长度无关；视图的视图共享同一缓冲区 |
| `mv[i]` | O(1) | O(1) | 将一个元素解包为 Python 对象；多维视图需要完整的索引元组 `mv[i, j]` |
| `mv[i] = v` | O(1) | O(1) | 仅限可写的一维视图，或使用完整的索引元组；只读视图抛出 `TypeError` |
| `mv[a:b]` | O(1) | O(1) | 同一内存上的另一个视图，与 `k` 无关；带步长的切片同样是视图 |
| `mv[a:b] = data` | O(k) | 连续时 O(1)，带步长时 O(k) | 仅限一维视图。复制 `k` 个元素进来；`data` 必须恰好有 `k` 个相同格式的元素，否则抛出 `ValueError` |
| `len(mv)` | O(1) | O(1) | 第一维的长度 |
| `bytes(mv)`, `mv.tobytes()` | O(n) | O(n) | 复制每个字节；非连续视图逐元素收集 |
| `mv == other` | O(n) | O(1) | 逐元素按值比较：`'i'` 格式的 `1` 等于 `'h'` 格式的 `1`，而 NaN 不等于任何值。形状不同时 O(1) 返回 `False`；大小比较抛出 `TypeError` |
| `hash(mv)` | O(n + e) | C 连续时 O(1)，否则 O(n) | 仅限格式为 `B`、`b` 或 `c` 的只读视图；导出者也会被哈希，因此未哈希过的 `bytes` 上的一小段切片仍要为整个 `bytes` 付出代价。结果被缓存，之后的调用为 O(1) |
| `for x in mv`, `x in mv` | O(n) | O(1) | 仅限一维视图；`in` 是线性扫描 |

## 方法

| 方法 | 时间 | 空间 | 备注 |
|--------|------|-------|-------|
| `tobytes(order='C')` | O(n) | O(n) | `order` 决定副本中元素的顺序，不影响其大小 |
| `tolist()` | O(n) | O(n) | 每个元素一个列表项，按维度嵌套；0 维视图直接返回其唯一的元素 |
| `hex(sep, bytes_per_sep)` | O(n) | O(n) | 每字节两个字符；非连续视图先复制自身 |
| `cast(format, shape)` | O(1) | O(1) | 重新解释同一块内存。仅限 C 连续视图，一侧必须是字节格式，总字节数不变，且源和新 `shape` 至少有一个是一维 |
| `toreadonly()` | O(1) | O(1) | 同一缓冲区上新的只读视图 |
| `release()` | O(1) | O(1) | 之后通过视图读写会抛出 `ValueError`；释放前 `bytearray` 导出者不能改变大小 |
| `count(value)` | O(n) | O(1) | 3.14+。比较每个元素；仅限一维视图 |
| `index(value, start, stop)` | O(n) | O(1) | 3.14+。在第一个匹配处停止；不存在时抛出 `ValueError`。仅限一维视图 |

## 属性

| 属性 | 时间 | 空间 | 备注 |
|-----------|------|-------|-------|
| `obj` | O(1) | O(1) | 导出者本身 |
| `nbytes` | O(1) | O(1) | `n * itemsize` |
| `readonly` | O(1) | O(1) | |
| `format` | O(1) | O(1) | `struct` 格式字符串，`bytes` 为 `'B'` |
| `itemsize` | O(1) | O(1) | 每个元素的字节数 |
| `ndim` | O(1) | O(1) | |
| `shape`, `strides`, `suboffsets` | O(ndim) | O(ndim) | `ndim > 0` 时 `shape` 和 `strides` 每次访问都新建一个元组；普通缓冲区的 `suboffsets` 为 `()` |
| `contiguous`, `c_contiguous`, `f_contiguous` | O(1) | O(1) | 在创建视图时计算好的标志 |

## 基本用法

### 来自 bytes

```python
# O(1) - create view, no copy
b = b"hello"
mv = memoryview(b)
mv.obj is b   # True

# Access elements
mv[0]      # 104 (ord('h'))
mv[1:3]    # <memory at 0x...> - slice is also an O(1) view
```

### 来自 bytearray

```python
# O(1) - create view
ba = bytearray(b"hello")
mv = memoryview(ba)

# Can modify through view
mv[0] = 72  # O(1) - changes 'h' to 'H'
print(ba)   # bytearray(b'Hello')
```

### 来自 array

```python
# O(1) - works with array module
import array

arr = array.array('i', [1, 2, 3, 4, 5])
mv = memoryview(arr)

# Elements are the exporter's, not bytes
mv[0]        # 1
mv.format    # 'i'
mv.itemsize  # 4
mv.nbytes    # 20
```

## 复杂度细节

### 不复制

```python
# O(1) - memoryview doesn't copy data
b = b"a" * 10000
mv = memoryview(b)  # O(1) - the view is the same size for any buffer

# vs creating a list copy
lst = list(b)  # O(n) - one list entry per byte
```

### 切片

```python
# O(1) - slice is just another view
ba = bytearray(b"hello world")
mv = memoryview(ba)

# Slice - also O(1), doesn't copy
world = mv[6:11]
world.obj is ba   # True

# Writes through the slice land in the original
world[0] = 87     # 'W'
print(ba)         # bytearray(b'hello World')
```

### 索引

```python
# O(1) - direct memory access
mv = memoryview(b"test")

# Read element
byte_val = mv[0]  # 116

# Write element (if mutable)
ba = bytearray(b"test")
mv = memoryview(ba)
mv[0] = 84  # O(1) - changes to 'T'
```

### 哈希与相等

```python
# O(n) - both walk every element
b = b"hello"
mv = memoryview(b)
mv == b                 # True
mv == mv[1:]            # False - O(1), the shapes differ

hash(mv) == hash(b)     # True; cached, so the second call is O(1)

# A writable view cannot be hashed
try:
    hash(memoryview(bytearray(b"hello")))
except ValueError:
    pass                # cannot hash writable memoryview object
```

### cast

```python
# O(1) - the same bytes, read as a different element type
raw = bytes(8)
as_ints = memoryview(raw).cast('i')
len(as_ints)      # 2
as_ints.nbytes    # 8, unchanged

# A shape turns a flat buffer into a matrix, still without copying
grid = memoryview(bytes(range(6))).cast('B', (2, 3))
grid.tolist()     # [[0, 1, 2], [3, 4, 5]] - O(n)
```

## 常见模式

### 零拷贝数据访问

```python
# O(1) - no memory copy
data = bytearray(b"binary data here")
view = memoryview(data)  # O(1)

# Process without copying
def process(view):
    for i in range(len(view)):
        print(view[i])

process(view)  # O(n) - one O(1) read per element
```

### 高效的二进制协议

```python
# O(1) - parse binary data without copying
binary_data = b"\x01\x02\x03\x04"
view = memoryview(binary_data)

# Parse header - O(1)
header_type = view[0]   # 1
header_version = view[1] # 2

# Parse payload - O(1) slice
payload = view[2:4]  # <memory>
```

### 切片赋值

```python
# O(1) - create view of mutable buffer
buffer = bytearray(1024)
view = memoryview(buffer)

# Modify through view
view[0:4] = b"HEAD"  # O(k) - copies 4 bytes in

# Read back
header = bytes(view[0:4])  # O(k) to convert to bytes

# The lengths must match
try:
    view[0:4] = b"HEADER"
except ValueError:
    pass  # lvalue and rvalue have different structures
```

### 高效的数据传输

```python
# O(1) - pass view instead of copying
def send_data(view):
    # view is O(1) to create, no copy of the data
    # Copy only when actually sending
    bytes_to_send = bytes(view)  # O(n)
    # network.send(bytes_to_send)

data = b"large data" * 1000
view = memoryview(data)  # O(1) - instant
# send_data(view)  # Efficient
```

## 性能模式

### 对比复制

```python
# Inefficient - copying
data = b"x" * 10**6
copy = data[100:200]  # O(k) - creates new bytes

# Efficient - memoryview
view = memoryview(data)  # O(1)
slice_view = view[100:200]  # O(1) - just a view
```

### 对比转换为列表

```python
# List conversion - O(n)
b = b"hello"
lst = list(b)  # [104, 101, 108, 108, 111]

# Memoryview - O(1)
mv = memoryview(b)  # O(1)
mv[0]  # 104
```

### 批处理

```python
def process_chunk(chunk):
    return sum(chunk)  # O(k) over the chunk's elements

# O(n) - process without copying
def process_chunks(data):
    mv = memoryview(data)  # O(1)

    # Process in chunks - O(n) total
    total = 0
    for i in range(0, len(mv), 1024):
        chunk = mv[i:i+1024]  # O(1) per chunk - just view
        total += process_chunk(chunk)
    return total

data = b"x" * 1000000
process_chunks(data)  # Efficient - no copies
```

## 实用示例

### 二进制文件处理

```python
import tempfile

with tempfile.TemporaryFile() as f:
    f.write(b"MAGC\x02" + bytes(11) + b"payload")
    f.seek(0)
    data = f.read()  # O(n) - the file is read once

mv = memoryview(data)  # O(1)

# Access header without copying
magic = bytes(mv[0:4])  # O(k) - only copy what is needed
version = mv[4]  # O(1)

# Process payload - O(1) view creation
payload = mv[16:]  # O(1)
```

### 网络协议解析器

```python
# O(1) - parse protocol messages
def parse_header(data):
    view = memoryview(data)  # O(1)

    # Extract fields - all O(1)
    msg_type = view[0]
    length = int.from_bytes(view[1:3], 'big')
    flags = view[3]

    return {
        'type': msg_type,
        'length': length,
        'flags': flags
    }

packet = b"\x01\x00\x10\xFF" + b"payload..."
header = parse_header(packet)  # {'type': 1, 'length': 16, 'flags': 255}
```

### 高效的缓冲区共享

```python
# O(1) - share buffer without copying
def fill_buffer(view, value):
    for i in range(len(view)):
        view[i] = value

buffer = bytearray(1000)
view = memoryview(buffer)  # O(1)

fill_buffer(view, 0)  # Fill with zeros - O(n)
# buffer is now filled
```

## 边界情况

### 空 memoryview

```python
# O(1)
mv = memoryview(b"")   # <memory at 0x...>
len(mv)  # 0
```

### 单个字节

```python
# O(1)
mv = memoryview(b"a")
mv[0]  # 97
```

### 不可变视图

```python
# O(1) - view of bytes (immutable)
mv = memoryview(b"hello")

# Cannot modify
try:
    mv[0] = 72
except TypeError:
    pass  # cannot modify read-only memory
```

### 可变视图

```python
# O(1) - view of bytearray (mutable)
ba = bytearray(b"hello")
mv = memoryview(ba)

# Can modify
mv[0] = 72  # O(1) - 'H'
print(ba)   # bytearray(b'Hello')
```

### 内存共享

```python
# O(1) - modifications visible in original
ba = bytearray(b"test")
mv = memoryview(ba)

# Modify through view
mv[0] = 84  # 'T'

# Changes visible in original
print(ba)   # bytearray(b'Test')

# Changes also visible in view
print(mv[0])  # 84
```

### 释放视图

```python
# O(1) - a live view pins a bytearray's size
ba = bytearray(b"test")
mv = memoryview(ba)

try:
    ba.append(33)
except BufferError:
    pass  # Existing exports of data: object cannot be re-sized

mv.release()   # O(1)
ba.append(33)  # fine now

try:
    mv[0]
except ValueError:
    pass  # operation forbidden on released memoryview object
```

## 转换操作

```python
# O(n) - convert memoryview to bytes
data = b"hello"
mv = memoryview(data)

# Convert to bytes
b = bytes(mv)  # O(n) - creates copy
# b'hello'

# Convert to list
lst = list(mv)  # O(n)
# [104, 101, 108, 108, 111]

# Hex string - two characters per byte
mv.hex()  # '68656c6c6f'
```

## 局限

```python
# O(1) - fast, but limited flexibility
mv = memoryview(b"hello")

# Can't concatenate directly
try:
    mv + mv
except TypeError:
    pass

# Must convert to bytes first
result = bytes(mv) + bytes(mv)  # O(n)

# Can't append - a view has a fixed size
hasattr(mv, "append")  # False
```

## 最佳实践

✅ **应该**：

- 使用 memoryview 实现零拷贝访问
- 创建 memoryview 以高效地传递给函数
- 使用切片高效获取子范围
- 仅在必要时转换为 bytes
- 在改变 `bytearray` 大小之前先释放其视图

❌ **避免**：

- 为一次性的短切片创建视图——视图对象本身比一小段 `bytes` 副本更大
- 假设 memoryview 的用法与 list 相同（API 不同）
- 尝试修改不可变缓冲区（bytes）
- 对可写视图或 `bytearray` 上的视图求哈希——两者都会抛出异常

## 相关函数

- **[bytes()](bytes_func.md)** - 不可变字节
- **[bytearray()](bytearray_func.md)** - 可变字节
- **[array](../stdlib/array.md)** - 类型化数组模块

## 版本说明

- **Python 3.12+**：可以用 Python 编写导出者，实现 `__buffer__()` 和
  `__release_buffer__()`；对 0 维视图调用 `len()` 抛出 `TypeError`
- **Python 3.14+**：新增 `count()` 和 `index()`；`memoryview[int]` 成为泛型别名
