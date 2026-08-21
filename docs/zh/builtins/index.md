---
source_sha: 08a4849b104da34098abb6cc5221e9047211c8b2131acaf75182af067ffb4cce
translated: machine
---

# 内置对象的复杂度

Python 无需导入即可使用的一切：内置类型、内置函数、常量以及异常体系。下面每一项都链接到
给出完整分析的页面；本页的表格给出主要复杂度，便于一眼找到所需内容。

## 内置类型

| 类型 | 适用场景 | 平均访问 | 平均插入 | 平均删除 |
|------|----------|-----------|-----------|-----------|
| `list` | 有序序列 | O(1) | O(n) | O(n) |
| `tuple` | 不可变序列 | O(1) | - | - |
| `range` | 数值序列 | O(1) | - | - |
| `str` | 文本 | O(1) | - | - |
| `bytes` | 二进制数据 | O(1) | - | - |
| `dict` | 键值映射 | O(1) | O(1) | O(1) |
| `set` | 唯一元素 | - | O(1) | O(1) |
| `frozenset` | 不可变的唯一元素 | - | - | - |

### 序列类型

- **[列表](list.md)** - 最灵活的序列类型
- **[元组](tuple.md)** - 不可变序列
- **[范围](range.md)** - 惰性求值的数值序列
- **[字符串](str.md)** - 文本与字符序列
- **[字节与字节数组](bytes.md)** - 二进制数据与可变字节

### 映射与集合类型

- **[字典](dict.md)** - 基于哈希的键值存储
- **[集合](set.md)** - 无序的唯一元素
- **[Frozenset](frozenset.md)** - 不可变的唯一元素

### 数值与布尔类型

- **[整数](int.md)** - 任意精度整数
- **[浮点数](float.md)** - IEEE 754 双精度
- **[布尔值](bool.md)** - 两个单例，`int` 的子类

## 内置函数

### 迭代

这一组函数返回迭代器。创建迭代器的开销很小；备注列中给出的开销是消耗该迭代器所需付出的代价。

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`iter()`](iter.md) | O(1) | O(1) | 把可迭代对象包装成迭代器 |
| [`next()`](next.md) | O(1)* | O(1) | * 开销取决于底层迭代器 |
| [`aiter()`](aiter.md) | O(1) | O(1) | `iter()` 的异步版本 |
| [`anext()`](anext.md) | O(1) | O(1) | await 的开销即异步生成器本身的开销 |
| [`enumerate()`](enumerate.md) | O(1) | O(1) | 消耗为 O(n)；产出 `(索引, 元素)` 元组 |
| [`zip()`](zip.md) | O(1) | O(1) | 消耗为 O(n)；在最短的可迭代对象处停止 |
| [`map()`](map.md) | O(1) | O(1) | 消耗为 O(n*k)，k 为函数耗时 |
| [`filter()`](filter.md) | O(1) | O(1) | 消耗为 O(n*k)，k 为谓词耗时 |
| [`reversed()`](reversed.md) | O(1) | O(1) | 消耗为 O(n)；需要 `__reversed__` 或 `__getitem__` |

### 聚合与排序

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`len()`](len.md) | O(1) | O(1) | 内置容器会缓存自身长度 |
| [`sum()`](sum.md) | O(n) | O(1) | 若误用于拼接字符串则为 O(n²) |
| [`min()`](min.md) | O(n) | O(1) | 必须比较每个元素 |
| [`max()`](max.md) | O(n) | O(1) | 必须比较每个元素 |
| [`sorted()`](sorted.md) | O(n log n) | O(n) | Timsort（≤3.10）、Powersort（3.11+） |
| [`all()`](all.md) | O(n) | O(1) | 遇到第一个假值即短路 |
| [`any()`](any.md) | O(n) | O(1) | 遇到第一个真值即短路 |

### 数值与进制

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`abs()`](abs.md) | O(1) | O(1) | 自定义 `__abs__()` 为 O(k) |
| [`divmod()`](divmod.md) | O(1) | O(1) | 任意精度整数为 O(n²) |
| [`pow()`](pow.md) | O(log y) | O(1) | 快速幂；三参数形式保持模运算 |
| [`round()`](round.md) | O(1) | O(1) | 恰为一半时采用银行家舍入 |
| [`bin()`](bin.md) | O(log n) | O(log n) | 开销即输出的长度 |
| [`hex()`](hex.md) | O(log n) | O(log n) | 开销即输出的长度 |
| [`oct()`](oct.md) | O(log n) | O(log n) | 开销即输出的长度 |

### 文本与字符

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`chr()`](chr.md) | O(1) | O(1) | 码位转字符 |
| [`ord()`](ord.md) | O(1) | O(1) | 字符转码位 |
| [`format()`](format.md) | O(n) | O(n) | n 为结果长度 |
| [`repr()`](repr.md) | O(n) | O(n) | 递归处理容器 |
| [`ascii()`](ascii.md) | O(n) | O(n) | 与 `repr()` 类似，但转义非 ASCII 字符 |
| [`hash()`](hash.md) | O(k) | O(1) | 字符串为 O(n)，首次调用后缓存 |

### 对象、属性与类型

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`type()`](type_func.md) | O(1) | O(1) | 三参数的建类形式为 O(n) |
| [`isinstance()`](isinstance.md) | O(d) | O(1) | d 为 MRO 深度；实际使用中相当于 O(1) |
| [`issubclass()`](issubclass.md) | O(d) | O(1) | d 为 MRO 深度；实际使用中相当于 O(1) |
| [`callable()`](callable.md) | O(1) | O(1) | 检查是否有 `__call__` |
| [`id()`](id.md) | O(1) | O(1) | `is` 运算符的基础 |
| [`getattr()`](getattr.md) | O(d) | O(1) | 命中实例字典时平均为 O(1) |
| [`setattr()`](setattr.md) | O(1) | O(1) | 哈希表插入 |
| [`hasattr()`](hasattr.md) | O(d) | O(1) | 与 `getattr()` 查找相同，只是捕获异常 |
| [`delattr()`](delattr.md) | O(1) | O(1) | 哈希表删除 |
| [`dir()`](dir.md) | O(n log n) | O(n) | 主要开销来自对结果排序 |
| [`vars()`](vars.md) | O(1) | O(1) | 返回 `__dict__` 的引用，不复制 |
| [`super()`](super.md) | O(d) | O(d) | 沿 MRO 查找，MRO 有缓存 |
| [`property()`](property.md) | O(1) | O(1) | 描述符的创建与访问 |
| [`classmethod()`](classmethod.md) | O(1) | O(1) | 创建描述符；查找为 O(d) |
| [`staticmethod()`](staticmethod.md) | O(1) | O(1) | 创建描述符；查找为 O(d) |

### 类型构造器

| 构造器 | 时间 | 空间 | 备注 |
|-------------|------|-------|-------|
| [`bool()`](bool_func.md) | O(1) | O(1) | 容器通过 `__len__()` 判断，该操作为 O(1) |
| [`int()`](int_func.md) | O(1) | O(1) | 解析很长的数字字符串时为 O(n²) |
| [`float()`](float_func.md) | O(1) | O(1) | 从字符串转换为 O(n) |
| [`complex()`](complex_func.md) | O(1) | O(1) | 从字符串转换为 O(n) |
| [`str()`](str_func.md) | O(1) | O(1) | 容器与自定义 `__str__()` 为 O(n) |
| [`bytes()`](bytes_func.md) | O(n) | O(n) | n 为来源的长度 |
| [`bytearray()`](bytearray_func.md) | O(n) | O(n) | n 为来源的长度 |
| [`memoryview()`](memoryview_func.md) | O(1) | O(1) | 缓冲区上的视图，从不复制 |
| [`list()`](list_func.md) | O(n) | O(n) | n 为可迭代对象的长度 |
| [`tuple()`](tuple_func.md) | O(n) | O(n) | 参数已经是元组时为 O(1) |
| [`dict()`](dict_func.md) | O(n) | O(n) | 哈希冲突下最坏为 O(n²) |
| [`set()`](set_func.md) | O(n) | O(n) | 哈希冲突下最坏为 O(n²) |
| [`frozenset()`](frozenset_func.md) | O(n) | O(n) | 参数已经是 frozenset 时为 O(1) |
| [`slice()`](slice.md) | O(1) | O(1) | 只保存索引；实际应用时为 O(k) |
| [`object()`](object_func.md) | O(1) | O(1) | 所有类的基类 |

### 代码执行

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`eval()`](eval.md) | O(n + m) | O(n + m) | n 为源码长度，m 为求值开销 |
| [`exec()`](exec.md) | O(n + m) | O(n + m) | n 为源码长度，m 为执行开销 |
| [`compile()`](compile.md) | O(n) | O(n) | 解析加上字节码生成 |
| [`globals()`](globals.md) | O(1) | O(1) | 返回已存在的模块字典 |
| [`locals()`](locals_func.md) | O(1) | O(1) | 在优化过的函数作用域中为 O(m) |

### 输入、输出与调试

| 函数 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`print()`](print.md) | O(n) | O(n) | n 为输出总长度；开销以 I/O 为主 |
| [`input()`](input.md) | O(k) | O(k) | k 为读取行的长度 |
| [`open()`](open.md) | O(1)* | O(1) | * 系统调用；读写的开销取决于数据量 |
| [`help()`](help.md) | O(n) | O(n) | n 为被检视接口的规模 |
| [`breakpoint()`](breakpoint.md) | O(1) | O(1) | 把控制权交给调试器 |

## 常量

| 常量 | 时间 | 空间 | 备注 |
|----------|------|-------|-------|
| [`None`](none.md) | O(1) | O(1) | 单例；用 `is` 比较 |
| [`True`](true.md) | O(1) | O(1) | 单例 `bool` |
| [`False`](false.md) | O(1) | O(1) | 单例 `bool` |
| [`NotImplemented`](notimplemented.md) | O(1) | O(1) | 运算符不支持该操作时返回 |
| [`Ellipsis`](ellipsis.md) | O(1) | O(1) | `...` 单例 |

## 异常与解释器

- **[异常](exceptions.md)** - 内置异常体系以及抛出与捕获的开销
- **[解释器信息](interpreter_info.md)** - `copyright`、`credits`、`license`
- **[Exit/Quit](exit_quit.md)** - `exit` 与 `quit`

## 核心概念

### 均摊复杂度

某些操作（如 `list.append()`）具有**均摊 O(1)** 复杂度，这意味着：

- 大多数追加操作是 O(1)
- 偶尔会触发一次需要 O(n) 的扩容
- 在大量操作上平均下来是 O(1)

### 惰性与急切

有几个内置函数返回的是迭代器而不是结果。无论输入多大，调用它们都是 O(1)；真正的工作发生在
消耗迭代器的过程中，被跳过的元素则完全不会产生开销。用 `list()` 包裹调用会让它重新变为急切
求值，并恢复 O(n) 的空间开销。

### 实现细节

CPython 使用：

- **列表**：带超额分配的动态数组
- **字典**：采用开放寻址的哈希表
- **集合**：哈希表（与字典类似）

## 版本说明

不同 Python 版本各有优化：

- **Python 3.7+**：字典的插入顺序得到保证（语言规范）
- **Python 3.9+**：新的字典实现带来改进
- **Python 3.10+**：对常见操作的进一步优化

按版本查看详细变更日志，请参见[版本](../versions/index.md)。

## 另请参阅

- [标准库](../stdlib/index.md)
- [实现](../implementations/index.md)
