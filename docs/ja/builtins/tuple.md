---
source_sha: c0bc8604cd865955e9bee5e9ce07ac587f5fc37659a6f2d952c5a11560725f18
translated: machine
---

# タプル操作の計算量

`tuple` 型は不変で順序を持つシーケンスです。不変であることが CPython でのさまざまな最適化を可能にしています。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接参照 |
| `access[i]` | O(1) | O(1) | 添字による直接アクセス |
| `index(x)` | O(n) | O(1) | 線形探索 |
| `count(x)` | O(n) | O(1) | 線形走査 |
| `in`（メンバーシップ） | O(n) | O(1) | 線形探索 |
| `copy()` | O(1) | O(1) | 参照カウントを増やすだけ |
| `x + y`（連結） | O(m+n) | O(m+n) | m と n はそれぞれの長さ |
| `t * n`（繰り返し） | O(n*len(t)) | O(n*len(t)) | 新しいタプルを作る |
| `hash()` | 初回 O(n)、キャッシュ後は O(1) | O(1) | ハッシュは一度計算されて `ob_hash` にキャッシュされる |
| `reversed()` | O(1) | O(1) | イテレータであり、実体化はしない |
| `tuple()` コンストラクタ | O(n) | O(n) | n はイテラブルの長さ |
| `slice [::2]` | O(k) | O(k) | k はスライスの長さ |

## 実装の詳細

### 不変であることの利点

```python
# Tuples are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### ハッシュの計算

```python
# hash() computes hash value by iterating all elements
t = (1, 2, 3)
h1 = hash(t)  # O(n) first call - computes by iterating elements

# CPython caches the hash in the tuple's ob_hash field
# Subsequent calls return the cached value
h2 = hash(t)  # O(1) - returns cached hash
```

### 参照とコピー

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
print(t1 is t2)  # True - same object in memory!

# This is safe because tuples are immutable
```

## リストとの性能比較

```python
# List access: O(1) with bounds checking
lst = [0] * 1000000
value = lst[500000]  # O(1)

# Tuple access: O(1) same as list
tup = tuple(lst)
value = tup[500000]  # O(1)

# But tuple creation from list: O(n)
tup = tuple(lst)  # O(n) - must copy all elements
```

## バージョン別の注記

- **すべてのバージョン**: 中心的な計算量は安定している
- **Python 3.8+**: 一部の場合でタプルのアンパックが改善
- **Python 3.11+**: 適応的な特殊化により、繰り返されるタプル操作が最適化されることがある

## 実装ごとの比較

### CPython
不変性に基づく最適化を備えた直接的なシーケンス型。

### PyPy
エスケープ解析を伴う JIT コンパイルによりさらに最適化される場合がある。

### Jython
Java の配列に支えられており、特性はほぼ同じ。

## ベストプラクティス

✅ **推奨**:

- 不変のシーケンスにはタプルを使う
- 構造を持つキーが必要なときは辞書のキーにタプルを使う
- 複数の戻り値にはタプルを使う
- タプルのアンパックを使う: `x, y = point`

❌ **避けるべきこと**:

- ループ内での連結の繰り返し（`t += (item,)`）- 代わりにリストを使う
- ループの中で大きなイテラブルからタプルを作る
- タプルのコピーが速いと思い込む - 同じ要素を参照しているだけである

## よくあるパターン

### 名前付きの戻り値

```python
# Basic tuples
def get_coordinates():
    return (10, 20)

x, y = get_coordinates()

# Better: use named tuples
from collections import namedtuple
Point = namedtuple('Point', ['x', 'y'])

def get_point():
    return Point(10, 20)

p = get_point()
print(p.x, p.y)  # More readable
```

### タプルとリストの性能

```python
# Tuple creation: O(n) once, then fast access
tup = tuple(range(1000000))
for i in range(1000):
    x = tup[i]  # O(1)

# List creation: O(n) once, then fast access
lst = list(range(1000000))
for i in range(1000):
    x = lst[i]  # O(1)

# Both have same access time; tuple is hashable and immutable
```

## 関連する型

- **[リスト](list.md)** - 可変の代替
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - 名前付きフィールドを持つタプル
- **[Dataclass](../stdlib/dataclasses.md)** - より高機能な構造の型

## さらに読む

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython のタプル実装を掘り下げた解説
