---
source_sha: d121e0a8af5ee71633a5877aead4146b5a677a147d64343c227a3ee27348715b
translated: machine
---

# len() 関数の計算量

`len()` 関数はコンテナオブジェクトに含まれる要素の個数を返します。

## 型ごとの計算量

| 型 | 時間 | 空間 | 備考 |
|------|------|-------|-------|
| `list` | O(1) | O(1) | 長さの属性を直接参照する |
| `tuple` | O(1) | O(1) | 不変なのでキャッシュされる |
| `dict` | O(1) | O(1) | サイズを保持している |
| `set` | O(1) | O(1) | サイズを保持している |
| `str` | O(1) | O(1) | 不変なのでキャッシュされる |
| `bytes` | O(1) | O(1) | 不変なのでキャッシュされる |
| `range` | O(1) | O(1) | 保持せずに計算する |
| `deque` | O(1) | O(1) | サイズを保持している |
| `defaultdict` | O(1) | O(1) | dict から継承している |
| `OrderedDict` | O(1) | O(1) | サイズを保持している |

## 組み込みのコンテナ型

組み込みのコンテナ型はすべて長さをキャッシュしており、定数時間で返します。

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

## 独自のオブジェクト

独自のクラスでは、`len()` は `__len__()` メソッドを呼び出します。

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

## ジェネレータ式とイテレータ

`len()` はジェネレータやイテレータには使えません。

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

## よくあるパターン

### コンテナが空かどうかの判定

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

### サイズの検証

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

### コンテナのサイズの比較

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

## 性能に関する注記

### ループ内での長さの取得

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

### 長さの事前計算

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

## 特殊なケース

### range オブジェクト

```python
# Range length is O(1), not O(n)
r = range(10**1000)
length = len(r)  # O(1) - computed from start, stop, step

# This is computed, not stored
# So even huge ranges have O(1) length
```

### 文字列のエンコーディング

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

## バージョン別の注記

- **Python 2.x**: `len()` は組み込み型と独自の `__len__` メソッドに対して働く
- **Python 3.x**: 挙動は同じで、より一貫している
- **すべてのバージョン**: 組み込みのコンテナでは O(1)（長さをキャッシュしているため）

## 関連する関数

- **[all()](all.md)** - すべての要素が真かどうかを調べる
- **[any()](any.md)** - いずれかの要素が真かどうかを調べる
- **[max()](max.md)** - 最大値を求める
- **[min()](min.md)** - 最小値を求める
- **[sum()](sum.md)** - すべての要素を合計する

## ベストプラクティス

✅ **推奨**:

- コンテナが空かどうかの判定に `len()` を使う（O(1) である）
- 真偽の判定には `if container:` を使う
- 長さのキャッシュは、きついループの中で何度も使う場合にだけ行う

❌ **避けるべきこと**:

- ジェネレータの要素数を数えるための `len(list(generator))`（O(n)）
- `__len__` の中で長さを計算し直す（キャッシュすべき）
- ジェネレータに長さがあると思い込む（存在しない）
