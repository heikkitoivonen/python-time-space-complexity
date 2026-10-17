---
source_sha: d68992f3f4de5abc5706af482d0525f0a95ba6718edc716dc1d6379f72e39aa0
translated: machine
---

# 字符串操作的复杂度

`str` 类型是由 Unicode 字符组成的不可变序列。CPython 以每个字符一个固定宽度存储每个字符串，宽度由其中最宽的字符决定，为 1、2 或 4 字节，因此索引是直接访问。由于字符串不能改变，复制一个类型恰好是 `str` 的字符串会返回该字符串本身。

`n` 是字符串长度，`m` 是字符串参数（`sub`、`prefix`、`sep`、`old`）的长度，`r` 是结果的长度，`k` 是重复次数，`w` 是请求的宽度，`c` 是 `chars` 参数的长度。`i:j` 是切片边界，按负值规范化之后计算。传入 `start` 和 `end` 参数时，`n` 是被搜索区域的长度，该区域原地读取而不会被复制。以比 `s` 更窄的宽度存储的多字符参数，例如含有 CJK 字符的文本中的 ASCII 子串，会先按 `s` 的宽度复制一份：搜索方法以及 `count()`、`replace()`、`split()`、`rsplit()`、`partition()` 和 `rpartition()` 因此需要 O(m) 的额外空间。

## 复杂度参考

### str

| 操作 | 时间 | 空间 | 说明 |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | 长度存储在字符串中，不需要计数 |
| `s[k]` | O(1) | O(1) | 直接索引；结果是单字符字符串 |
| `s[i:j]`（切片） | O(j-i) | O(j-i) | 带步长时为 O(r)；类型恰好是 `str` 时 `s[:]` 返回 `s` 本身 |
| `s[:]`, `str(s)`, `copy.copy(s)` | O(1) | O(1) | 当 `s` 类型恰好是 `str` 时返回 `s` 本身；子类实例以 O(n) 复制 |
| `s + t`（拼接） | O(n+len(t)) | O(n+len(t)) | 一方为空时返回另一个操作数本身；在循环中用 `+=` 构建字符串最坏为 O(r²) |
| `s * k`（重复） | O(nk) | O(nk) | k ≤ 0 得到空字符串；`s * 1` 返回 `s` 本身 |
| `s == t` | O(n) | O(1) | 长度或字符宽度不同，或两者是同一个对象时为 O(1) |
| `s < t`, `<=`, `>`, `>=` | O(min(n, len(t))) | O(1) | 在第一个不相等的字符处停止 |
| `hash(s)` | 首次调用 O(n)；之后 O(1) | O(1) | 结果保存在字符串中；另外构建的相等字符串要付出它自己的首次哈希开销 |
| `for c in s` | O(n) | O(1) | 每一步一个单字符字符串 |
| `sub in s`（子串） | O(n) | O(1)，加宽时 O(m) | 最坏情况为线性的正向搜索；比字符串更长的子串立即返回 |
| **搜索** ||||
| `find(sub, start, end)` | O(n) | O(1)，加宽时 O(m) | 正向搜索；n = 被搜索的字符数 |
| `rfind(sub, start, end)` | 最坏 O(n·m) | O(1)，加宽时 O(m) | 反向搜索；典型输入下为 O(n) |
| `index(sub, start, end)` | O(n) | O(1)，加宽时 O(m) | 与 `find()` 相同，但找不到时抛出 `ValueError` |
| `rindex(sub, start, end)` | 最坏 O(n·m) | O(1)，加宽时 O(m) | 与 `rfind()` 相同，但找不到时抛出 `ValueError` |
| `count(sub, start, end)` | O(n) | O(1)，加宽时 O(m) | 正向搜索 |
| `startswith(prefix)` | O(m) | O(1) | 只比较前缀 |
| `endswith(suffix)` | O(m) | O(1) | 只比较后缀 |
| **替换/转换** ||||
| `replace(old, new)` | O(n + r) | O(r)，加宽时 O(m) | 正向搜索 `old`；`old` 不出现时返回 `s` 本身 |
| `translate(table)` | O(n + r) | O(n + r) | 每次表查找按 O(1) 计；映射到更长字符串会使 r 超过 n |
| `str.maketrans(x, y, z)` | O(e) | O(e) | e = 参数中的字符数或字典条目数；静态方法 |
| `expandtabs(tabsize)` | O(n + r) | O(r) | 每个制表符使结果最多增加 `tabsize` 个字符；没有制表符时返回 `s` 本身 |
| `removeprefix(prefix)` | O(n) | O(n) | `prefix` 匹配时复制其余部分；否则为 O(m) 并返回 `s` 本身 |
| `removesuffix(suffix)` | O(n) | O(n) | `suffix` 匹配时复制其余部分；否则为 O(m) 并返回 `s` 本身 |
| **分割/连接** ||||
| `split(sep)` | O(n) | O(n) | 正向搜索 `sep` |
| `rsplit(sep)` | 最坏 O(n·m) | O(n) | 像 `rfind()` 一样反向搜索；没有 `sep` 或 `sep` 为单个字符时为 O(n) |
| `splitlines()` | O(n) | O(n) | 按行边界分割 |
| `partition(sep)` | O(n) | O(n) | 正向搜索第一个 `sep` |
| `rpartition(sep)` | 最坏 O(n·m) | O(n) | 像 `rfind()` 一样反向搜索 |
| `sep.join(iterable)` | O(r + p) | O(r + p) | p = 片段数；既不是列表也不是元组的可迭代对象会先被收集成列表；只有一个类型恰好是 `str` 的片段时返回该片段本身 |
| **大小写转换** ||||
| `upper()` | O(n) | O(n) | |
| `lower()` | O(n) | O(n) | |
| `capitalize()` | O(n) | O(n) | 首字符转为标题大小写，其余转为小写 |
| `title()` | O(n) | O(n) | 每个单词转为标题大小写 |
| `swapcase()` | O(n) | O(n) | |
| `casefold()` | O(n) | O(n) | 用于不区分大小写的匹配 |
| **去除** ||||
| `strip(chars)` | O(n + (d+1)·c) | O(n) | d = 被去除的字符数，每个都要在 `chars` 中查找；没有可去除的字符时返回 `s` 本身 |
| `lstrip(chars)` | O(n + (d+1)·c) | O(n) | 同 `strip()`，从左侧 |
| `rstrip(chars)` | O(n + (d+1)·c) | O(n) | 同 `strip()`，从右侧 |
| **填充/对齐** ||||
| `center(width)` | O(w) | O(w) | w ≤ n 时返回 `s` 本身 |
| `ljust(width)` | O(w) | O(w) | w ≤ n 时返回 `s` 本身 |
| `rjust(width)` | O(w) | O(w) | w ≤ n 时返回 `s` 本身 |
| `zfill(width)` | O(w) | O(w) | w ≤ n 时返回 `s` 本身 |
| **判断** ||||
| `isalnum()` | O(n) | O(1) | |
| `isalpha()` | O(n) | O(1) | |
| `isascii()` | O(1) | O(1) | 读取 `str` 保存的一个标志 |
| `isdecimal()` | O(n) | O(1) | |
| `isdigit()` | O(n) | O(1) | |
| `isidentifier()` | O(n) | O(1) | |
| `islower()` | O(n) | O(1) | |
| `isnumeric()` | O(n) | O(1) | |
| `isprintable()` | O(n) | O(1) | |
| `isspace()` | O(n) | O(1) | |
| `istitle()` | O(n) | O(1) | |
| `isupper()` | O(n) | O(1) | |
| **格式化** ||||
| `format(*args, **kwargs)` | O(n) + 每个字段的 `format()` | O(n) + 每个字段的 `format()` | n = 模板长度；见 [format()](format.md) |
| `format_map(mapping)` | O(n) + 每个字段的 `format()` | O(n) + 每个字段的 `format()` | 与 `format()` 相同，但使用映射 |
| `s % values` | O(n) + 每次转换 | O(n) + 每次转换 | `%s` 调用 `str()`；见 [format()](format.md) |
| **编码** ||||
| `encode(encoding)` | O(n) | O(n) | 转换为字节串；假设编解码器对每个字符做常数量的工作 |

## 复制返回同一个字符串

类型恰好是 `str` 的字符串，其副本不可能与原字符串不同，因此 `s[:]`、`str(s)` 和 `copy.copy(s)` 以 O(1) 返回 `s` 本身。有几个方法在没有需要改变的内容时也这样做：填充到不大于字符串长度的宽度、没有匹配可去除时的去除操作、`old` 不出现时的 `replace()`，以及只有一个字符串的 `join()`。子类实例以 O(n) 复制。

```python
import copy

s = "x" * 1_000_000
assert s[:] is s  # O(1)
assert str(s) is s  # O(1)
assert copy.copy(s) is s  # O(1)

assert s.center(10) is s  # w <= n
assert s.strip() is s  # nothing to strip
assert s.replace("y", "z") is s  # "y" does not occur
assert "".join([s]) is s  # a single piece


class Text(str):
    pass


t = Text("abc")
assert str(t) is not t and type(str(t)) is str  # O(n): a subclass is copied
```

## 字符宽度

每个字符串都以其最宽字符所需的宽度存储：U+00FF 以内每个字符 1 字节，U+FFFF 以内 2 字节，超出则 4 字节。只要有一个宽字符，整个字符串就会变宽，这就是更窄的子串在搜索前必须先加宽的原因。

```python
import sys


def bytes_per_char(ch):
    return (sys.getsizeof(ch * 2_000) - sys.getsizeof(ch * 1_000)) // 1_000


assert bytes_per_char("a") == 1
assert bytes_per_char("é") == 1
assert bytes_per_char("世") == 2
assert bytes_per_char("😀") == 4

# One CJK character makes all 1,000 ASCII characters take 2 bytes each
assert sys.getsizeof("世" + "a" * 1_000) - sys.getsizeof("世") == 2_000
```

## 构建字符串

两个非空字符串的每次 `+` 都会构建一个新字符串，因此 `+=` 循环可能在每一步复制到目前为止构建的全部内容，总长度上为 O(r²)。CPython 有时可以改为原地扩展字符串，但只限于没有其他东西引用它的时候：只要对部分结果还保留任何其他引用，每一步都会复制。`join()` 一次确定结果大小，并把每个片段各复制一次。

```python
pieces = [str(i) for i in range(10_000)]

joined = "".join(pieces)  # O(r + p)

built = ""
for piece in pieces:
    built += piece  # O(r²) at worst

assert built == joined
```

## 子串搜索

正向搜索（`in`、`find()`、`index()`、`count()`，以及 `split()`、`partition()` 和 `replace()` 中的搜索）最坏情况为线性。反向搜索（`rfind()`、`rindex()`、`rsplit()`、`rpartition()`）在典型输入下为 O(n)，最坏为 O(n·m)。传入 `start` 和 `end` 时只读取该区域，并且与先切片不同，不会复制任何内容。

```python
s = "a" * 1_000_000 + "b"

assert s.find("b") == 1_000_000  # O(n)
assert s.find("b", 0, 1_000) == -1  # O(1,000): only the region is read
assert "a" * 999 + "b" in s  # O(n), however long the pattern
assert s.rfind("ba") == -1  # O(n) here, O(n·m) at worst
```

## 性能最佳实践

✅ **推荐**：

- 用 `"".join(pieces)` 从许多片段构建字符串：一次 O(r + p)
- 向 `find()` 或 `count()` 传入 `start` 和 `end`，而不是先切片：区域原地读取，而切片会复制 O(j-i) 个字符
- 对长模式优先使用正向搜索而不是反向搜索：O(n) 对比最坏 O(n·m)

❌ **避免**：

- 在遍历许多片段的循环中使用 `+=`，尤其是在对部分字符串还存在其他引用时
- 给 `strip()` 传入很长的 `chars` 参数：每个被去除的字符都要在 `chars` 中查找

## 相关类型

- **[Bytes](bytes.md)** - 不可变字节序列
- **[Bytearray](bytearray.md)** - 可变字节序列
- **[str()](str_func.md)** - 将对象转换为字符串
- **[format()](format.md)** - f-string、`str.format()` 和 `%` 格式化
- **[正则表达式 (re)](../stdlib/re.md)** - 模式匹配

## 延伸阅读

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  深入了解 CPython 的字符串实现
