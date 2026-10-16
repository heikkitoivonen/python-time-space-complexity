---
source_sha: 94b8516e62742f8991e48fca56d762ca55a09160a862913d1a31bbcba081e372
translated: machine
---

# タプル操作の計算量

`tuple` 型は不変で順序を持つシーケンスです。不変であることが CPython でのさまざまな最適化を可能にしています。

`n` はタプルの長さ、`k` は添字または繰り返し回数、`i:j` はスライスの範囲、`len(t1)`、`len(t2)` はオペランドの長さです。要素 1 つの比較やハッシュは O(1) とみなします。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | 長さはタプルに格納されており、数え直さない |
| `t[k]` | O(1) | O(1) | 添字による直接アクセス |
| `index(x)` | O(n) | O(1) | 線形探索 |
| `count(x)` | O(n) | O(1) | 線形走査 |
| `x in t`（メンバーシップ） | O(n) | O(1) | 線形探索 |
| `tuple(t)`, `copy.copy(t)` | O(1) | O(1) | `t` が厳密に `tuple` 型なら `t` 自身を返す。タプルには `copy()` メソッドはない |
| `t1 + t2`（連結） | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k`（繰り返し） | O(nk) | O(nk) | |
| `for x in t`（反復） | O(n) | O(1) | 1 ステップあたり O(1) |
| `min(t)`, `max(t)` | O(n) | O(1) | 比較は n-1 回 |
| `hash()` | 初回 O(n)、3.14 以降はその後 O(1) | O(1) | 3.14 以降はハッシュを `ob_hash` にキャッシュする。3.11〜3.13 は呼び出すたびに再計算する |
| `reversed()` | O(1) | O(1) | イテレータであり、実体化はしない |
| `tuple()` コンストラクタ | O(n) | O(n) | n はイテラブルの長さ。厳密に `tuple` 型の引数はそのまま返される |
| `t[i:j]`（スライス） | O(j-i) | O(j-i) | ステップ付きでは O(結果の長さ) |

## 実装の詳細

### 不変であることの利点

```python
# Tuples of hashable elements are hashable - can be dict keys or set members
d = {(1, 2): 'point', (3, 4): 'another'}
s = {(0, 0), (1, 1)}

# Lists cannot - they're mutable
# d[[1, 2]] = 'fails'  # TypeError: unhashable type
```

### ハッシュの計算

```python
# hash() computes hash value by iterating all elements
t = tuple([1, 2, 3])  # built at run time, so not hashed yet
h1 = hash(t)  # O(n) first call - computes by iterating elements

# Python 3.14+ caches the hash in the tuple's ob_hash field;
# 3.11-3.13 recompute it on every call
h2 = hash(t)  # O(1) on 3.14+, O(n) on 3.11-3.13
assert h1 == h2
```

### 参照とコピー

```python
# Tuple "copy" doesn't copy - returns same object
t1 = (1, 2, 3)
t2 = tuple(t1)
assert t1 is t2  # True - same object in memory!

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

- **Python 3.8+**: 一部の場合でタプルのアンパックが改善
- **Python 3.11+**: 適応的な特殊化により、繰り返されるタプル操作が最適化されることがある
- **Python 3.14+**: `hash()` は結果をタプルにキャッシュするため、2 回目以降の呼び出しは O(1)

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

# Both have O(1) indexing; tuple is hashable and immutable
```

## 関連する型

- **[リスト](list.md)** - 可変の代替
- **[Namedtuple](../stdlib/collections.md#namedtuple)** - 名前付きフィールドを持つタプル
- **[Dataclass](../stdlib/dataclasses.md)** - より高機能な構造の型

## さらに読む

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython のタプル実装を掘り下げた解説
