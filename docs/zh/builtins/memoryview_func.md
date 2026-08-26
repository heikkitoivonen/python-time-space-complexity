---
source_sha: 26ab06b2234ef5af328ca310db336739cfcd9de23fad475459c794b9a4449591
translated: machine
---

# memoryview() 函数的复杂度

`memoryview()` 函数在不拷贝数据的情况下创建字节类对象的内存视图。

## 复杂度分析

| 操作 | 时间 | 空间 | 备注 |
|------|------|-------|-------|
| 创建 memoryview | O(1) | O(1) | 仅创建视图，不拷贝底层数据 |
| 索引访问 | O(1) | O(1) | 直接内存访问 |
| 切片 | O(1) | O(1) | 创建新的视图对象，不拷贝数据 |
| `bytes(mv)` 转换 | O(n) | O(n) | n = 视图大小；拷贝数据 |
| 修改 | O(1) | O(1) | 仅当底层缓冲区可变时（如 bytearray） |

## 方法

| 方法 | 时间 | 空间 | 备注 |
|--------|------|-------|-------|
| `tobytes()` | O(n) | O(n) | 转换为 bytes 对象 |
| `tolist()` | O(n) | O(n) | 转换为元素列表 |
| `toreadonly()` | O(1) | O(1) | 返回视图的只读版本 |
| `release()` | O(1) | O(1) | 释放底层缓冲区 |
| `cast(format)` | O(1) | O(1) | 重新解释为不同类型；字节大小必须相同 |
| `hex()` | O(n) | O(n) | 返回十六进制字符串表示 |
| `count(value)` | O(n) | O(1) | 统计 value 出现的次数 |
| `index(value)` | O(n) | O(1) | 查找 value 的第一个索引；未找到时抛出 ValueError |

## 属性

| 属性 | 时间 | 备注 |
|-----------|------|-------|
| `obj` | O(1) | memoryview 引用的底层对象 |
| `nbytes` | O(1) | 视图中的总字节数 |
| `readonly` | O(1) | 布尔值，指示内存是否只读 |
| `format` | O(1) | 结构体格式字符串（如 'B' 表示无符号字节） |
| `itemsize` | O(1) | 每个元素的字节大小 |
| `ndim` | O(1) | 维度数量 |
| `shape` | O(1) | 各维度大小的元组 |
| `strides` | O(1) | 每个维度步进的字节数元组 |
| `suboffsets` | O(1) | 用于 PIL 风格数组的元组；简单缓冲区为 None |
| `contiguous` | O(1) | 布尔值；C 或 Fortran 连续时为 True |
| `c_contiguous` | O(1) | 布尔值；“C 序”连续时为 True |
| `f_contiguous` | O(1) | 布尔值；“Fortran 序”连续时为 True |

## 基本用法

### 从 bytes 创建

```python
# O(1) - create view, no copy
b = b"hello"
mv = memoryview(b)
# <memory at 0x...>

# Access elements
mv[0]      # 104 (ord('h'))
mv[1:3]    # <memory at 0x...> - slice is also O(1) view
```

### 从 bytearray 创建

```python
# O(1) - create view
ba = bytearray(b"hello")
mv = memoryview(ba)

# Can modify through view
mv[0] = 72  # O(1) - changes 'h' to 'H'
print(ba)   # bytearray(b'Hello')
```

### 从 array 创建

```python
# O(1) - works with array module
import array

arr = array.array('i', [1, 2, 3, 4, 5])
mv = memoryview(arr)

# Access as view
mv[0]  # 1
```

## 复杂度细节

### 无拷贝

```python
# O(1) - memoryview doesn't copy data
b = b"a" * 10000
mv = memoryview(b)  # O(1) - instant, no copy

# vs creating a list copy
lst = list(b)  # O(n) - creates list

# View uses original memory
```

### 切片

```python
# O(1) - slice is just another view
b = b"hello world"
mv = memoryview(b)

# Original view
mv[0]      # 104

# Slice - also O(1), doesn't copy
slice_view = mv[6:11]  # <memory at 0x...> - "world"

# Can modify through slice (if writable)
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

process(view)  # Efficient - no copy
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

### 内存映射

```python
# O(1) - create view of mutable buffer
buffer = bytearray(1024)
view = memoryview(buffer)

# Modify through view
view[0:4] = b"HEAD"  # O(4) - copy 4 bytes

# Read back
header = bytes(view[0:4])  # O(4) to convert to bytes
```

### 高效数据传输

```python
# O(1) - pass view instead of copying
def send_data(view):
    # view is O(1) to create, no memory allocation
    # Copy only when actually sending
    bytes_to_send = bytes(view)  # O(n)
    # network.send(bytes_to_send)

data = b"large data" * 1000
view = memoryview(data)  # O(1) - instant
# send_data(view)  # Efficient
```

## 性能典范

### 对比拷贝

```python
# Inefficient - copying
data = b"x" * 10**6
copy = data[100:200]  # O(100) - creates new bytes

# Efficient - memoryview
view = memoryview(data)  # O(1)
slice_view = view[100:200]  # O(1) - just a view
```

### 对比列表转换

```python
# List conversion - O(n)
b = b"hello"
lst = list(b)  # O(5) - [104, 101, 108, 108, 111]

# Memoryview - O(1)
mv = memoryview(b)  # O(1)
mv[0]  # 104
```

### 批量处理

```python
# O(n) - process without copying
def process_chunks(data):
    mv = memoryview(data)  # O(1)
    
    # Process in chunks - O(n) total
    for i in range(0, len(mv), 1024):
        chunk = mv[i:i+1024]  # O(1) per chunk - just view
        process_chunk(chunk)  # Process view

data = b"x" * 1000000
process_chunks(data)  # Efficient - no copies
```

## 实际示例

### 二进制文件处理

```python
# O(1) - create view of file data
with open("large.bin", "rb") as f:
    data = f.read()

mv = memoryview(data)  # O(1)

# Access header without copying
magic = bytes(mv[0:4])  # O(4) - only copy what needed
version = mv[4]  # O(1)

# Process payload - O(1) view creation
payload = mv[16:]  # O(1)
```

### 图像数据处理

```python
# O(1) - view image pixels
from PIL import Image

img = Image.open("photo.png")
img_bytes = img.tobytes()  # Get raw pixel data

mv = memoryview(img_bytes)  # O(1) view

# Access pixel - O(1)
pixel_r = mv[0]  # Red component
pixel_g = mv[1]  # Green component
pixel_b = mv[2]  # Blue component
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
header = parse_header(packet)
```

### 高效缓冲区共享

```python
# O(1) - share buffer without copying
def fill_buffer(view, value):
    for i in range(len(view)):
        view[i] = value

buffer = bytearray(1000)
view = memoryview(buffer)  # O(1)

fill_buffer(view, 0)  # Fill with zeros - O(1000)
# buffer is now filled
```

## 边界情况

### 空的 memoryview

```python
# O(1)
mv = memoryview(b"")   # <memory at 0x...>
len(mv)  # 0
```

### 单字节

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
# mv[0] = 72  # TypeError - read-only buffer

# But can create view
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

## 转换操作

```python
# O(n) - convert memoryview to bytes
data = b"hello"
mv = memoryview(data)

# Convert to bytes
b = bytes(mv)  # O(5) - creates copy
# b'hello'

# Convert to list
lst = list(mv)  # O(5)
# [104, 101, 108, 108, 111]
```

## 限制

```python
# O(1) - fast, but limited flexibility
mv = memoryview(b"hello")

# Can't concatenate directly
# mv + mv  # TypeError

# Must convert to bytes first
result = bytes(mv) + bytes(mv)  # O(2n)

# Can't append
# mv.append(33)  # AttributeError
```

## 最佳实践

✅ **应该**：

- 使用 memoryview 进行零拷贝访问
- 创建 memoryview 以便高效地传给函数
- 使用切片高效获取子范围
- 仅在必要时转换为 bytes

❌ **避免**：

- 为单次访问使用 memoryview（开销不值得）
- 假设 memoryview 像 list 一样工作（API 不同）
- 尝试修改不可变缓冲区（bytes）
- 为很小的数据创建 memoryview

## 相关函数

- **[bytes()](bytes_func.md)** - 不可变字节
- **[bytearray()](bytearray_func.md)** - 可变字节
- **[array](https://docs.python.org/3/library/array.html)** - 类型化数组模块

## 版本说明

- **Python 2.x**：memoryview() 可用（2.7 版本加入）
- **Python 3.x**：改进的 memoryview，支持切片
- **所有版本**：类字节对象的零拷贝视图
