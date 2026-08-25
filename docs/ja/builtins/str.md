---
source_sha: ea4f8b32c47a9951d364d070e44ddc25ab93c4bb79e0e11e0590f61fa3c0e688
translated: machine
---

# 文字列操作の計算量

`str` 型は Unicode 文字の不変なシーケンスです。Python の文字列は、特に Python 3 で大きく最適化されてきました。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接参照 |
| `access[i]` | O(1) | O(1) | 添字による直接アクセス |
| `in`（部分文字列） | 平均 O(n + m) | O(1) | CPython では Two-Way / fastsearch アルゴリズムを使う |
| `s + s`（連結） | O(n+m) | O(n+m) | 新しい文字列を作る |
| `s * n`（繰り返し） | O(n\*len(s)) | O(n\*len(s)) | 新しい文字列を作る |
| `slice [::2]` | O(k) | O(k) | k はスライスの長さ |
| **探索** ||||
| `find(sub)` | 平均 O(n + m) | O(1) | CPython では Two-Way / fastsearch アルゴリズムを使う |
| `rfind(sub)` | 最悪 O(n*m) | O(1) | 後方向の Boyer-Moore-Horspool を使う |
| `index(sub)` | O(n + m) | O(1) | find() と同じだが、見つからないと ValueError を送出する |
| `rindex(sub)` | 最悪 O(n*m) | O(1) | rfind() と同じだが、見つからないと ValueError を送出する |
| `count(sub)` | 平均 O(n + m) | O(1) | n は文字列、m は部分文字列 |
| `startswith(prefix)` | O(m) | O(1) | m は接頭辞の長さ |
| `endswith(suffix)` | O(m) | O(1) | m は接尾辞の長さ |
| **置換・変換** ||||
| `replace(old, new)` | O(n) | O(n) | 一度の走査 |
| `translate(table)` | O(n) | O(n) | 表を引きながら一度の走査 |
| `maketrans()` | O(k) | O(k) | k は対応の個数、静的メソッド |
| `expandtabs(tabsize)` | O(n) | O(n) | タブを空白に置き換える |
| `removeprefix(prefix)` | O(n) | O(n) | 接頭辞が一致すればスライスを返す |
| `removesuffix(suffix)` | O(n) | O(n) | 接尾辞が一致すればスライスを返す |
| **分割・連結** ||||
| `split(sep)` | O(n) | O(n) | 一度の走査 |
| `rsplit(sep)` | O(n) | O(n) | 右から分割する |
| `splitlines()` | O(n) | O(n) | 行の境界で分割する |
| `partition(sep)` | O(n) | O(n) | 最初の sep で 3 要素のタプルに分割する |
| `rpartition(sep)` | O(n) | O(n) | 最後の sep で 3 要素のタプルに分割する |
| `join(iterable)` | O(n) | O(n) | n は出力全体の文字数 |
| **大文字・小文字の変換** ||||
| `upper()` | O(n) | O(n) | すべての文字を処理する必要がある |
| `lower()` | O(n) | O(n) | すべての文字を処理する必要がある |
| `capitalize()` | O(n) | O(n) | 先頭を大文字に、残りを小文字にする |
| `title()` | O(n) | O(n) | 単語ごとに先頭を大文字にする |
| `swapcase()` | O(n) | O(n) | 大文字と小文字を入れ替える |
| `casefold()` | O(n) | O(n) | 大文字小文字を無視した比較のための強い小文字化 |
| **前後の除去** ||||
| `strip(chars)` | O(n) | O(n) | 両端から取り除く |
| `lstrip(chars)` | O(n) | O(n) | 左から取り除く |
| `rstrip(chars)` | O(n) | O(n) | 右から取り除く |
| **詰め物と揃え** ||||
| `center(width)` | O(n) | O(n) | 両側を埋める |
| `ljust(width)` | O(n) | O(n) | 右側を埋める |
| `rjust(width)` | O(n) | O(n) | 左側を埋める |
| `zfill(width)` | O(n) | O(n) | ゼロで埋める |
| **述語** ||||
| `isalnum()` | O(n) | O(1) | 英数字かどうかを調べる |
| `isalpha()` | O(n) | O(1) | 英字かどうかを調べる |
| `isascii()` | O(n) | O(1) | ASCII かどうかを調べる（Python 3.7+） |
| `isdecimal()` | O(n) | O(1) | 十進数字かどうかを調べる |
| `isdigit()` | O(n) | O(1) | 数字かどうかを調べる |
| `isidentifier()` | O(n) | O(1) | 妥当な識別子かどうかを調べる |
| `islower()` | O(n) | O(1) | 小文字かどうかを調べる |
| `isnumeric()` | O(n) | O(1) | 数値を表す文字かどうかを調べる |
| `isprintable()` | O(n) | O(1) | 印字可能かどうかを調べる |
| `isspace()` | O(n) | O(1) | 空白かどうかを調べる |
| `istitle()` | O(n) | O(1) | タイトルケースかどうかを調べる |
| `isupper()` | O(n) | O(1) | 大文字かどうかを調べる |
| **書式化** ||||
| `format(*args)` | O(n) | O(n) | n はテンプレートの長さ |
| `format_map(mapping)` | O(n) | O(n) | マッピングを使う format() と同じ |
| **エンコーディング** ||||
| `encode(encoding)` | O(n) | O(n) | バイト列に変換する |

## 実装の詳細

### 文字列のインターン

```python
# Small strings and identifiers are interned (reused)
s1 = "hello"
s2 = "hello"
print(s1 is s2)  # Likely True - same object

# Large strings are not interned
s3 = "x" * 1000
s4 = "x" * 1000
print(s3 is s4)  # False - different objects
```

### Python 3 の Unicode 最適化

```python
# Python 3 uses adaptive string representation
# ASCII strings use less memory than full Unicode

# Compact representation for ASCII
s = "hello"  # Uses 1 byte per character

# Full Unicode representation
s = "hello 世界"  # Uses more bytes for non-ASCII
```

### 文字列連結の性能

```python
# Inefficient: O(n²) - creates new strings repeatedly
result = ""
for i in range(10000):
    result += str(i)  # Copies entire string each time

# Efficient: O(n) - single allocation
result = "".join(str(i) for i in range(10000))
```

## 進んだ機能

### 部分文字列の探索

```python
# Linear time on average for substring search
s = "a" * 1000000 + "b"
result = s.find("b")  # Usually O(n) avg, not O(n²)

# CPython uses optimized algorithms (similar to Boyer-Moore)
```

## バージョン別の注記

| バージョン | 変更点 |
|---------|--------|
| Python 3.0+ | 既定で Unicode になる |
| Python 3.3+ | 柔軟な文字列表現（PEP 393） |
| Python 3.8+ | f-string の性能改善 |
| Python 3.11+ | 文字列操作の高速化とインライン化の改善 |

## 実装ごとの比較

### CPython
文字列のインターンと柔軟な表現により高度に最適化されている。

### PyPy
JIT コンパイルにより、繰り返される操作がさらに最適化される。

### Jython
Java の文字列に支えられており、性能特性はほぼ同じ。

## ベストプラクティス

✅ **推奨**:

- 複数の文字列をつなぐには `str.join()` を使う
- 書式化には f-string を使う（Python 3.6+）
- 部分文字列の判定には `in` を使う（平均 O(n)）
- 効率的な加工には `.find()` と `.replace()` を使う

❌ **避けるべきこと**:

- ループの中で `+` による文字列連結を行う
- `.replace()` を何度も呼ぶ - 一度で済ませるか正規表現を使う
- 入れ子のループの中で、キャッシュせずに `in` でメンバーシップを調べる
- 中間的な文字列オブジェクトを大量に作る

## よくあるパターン

### 効率的な文字列の組み立て

```python
# Bad: O(n²)
result = ""
for word in words:
    result += word

# Good: O(n)
result = "".join(words)

# Also good: list comprehension with join
result = "".join([w.upper() for w in words])
```

### 文字列の書式化

```python
# Python 3.6+ f-strings (preferred)
name = "World"
message = f"Hello, {name}!"  # Efficient and readable

# Older style (still works)
message = "Hello, {}!".format(name)

# Avoid %
message = "Hello, %s!" % name
```

### パターンマッチング

```python
# Use str methods for simple patterns
if s.startswith("test_"):  # O(m) where m = prefix length
    pass

# Use regex for complex patterns
import re
pattern = re.compile(r"test_\d+")  # Compile once
if pattern.match(s):  # Reuse compiled pattern
    pass
```

## 関連する型

- **[バイト列](bytes_func.md)** - 不変のバイトのシーケンス
- **[バイト配列](bytearray_func.md)** - 可変のバイトのシーケンス
- **[正規表現 (re)](../stdlib/re.md)** - パターンマッチング

## さらに読む

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython の文字列実装を掘り下げた解説
