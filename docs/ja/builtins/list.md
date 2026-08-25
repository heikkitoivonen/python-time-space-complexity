---
source_sha: 2c9b1483aa05e2e0dbb6693a2258ac1a811fbbbb06b82e37147b372fe2ca1fc9
translated: machine
---

# リスト操作の計算量

`list` 型は可変で順序を持つシーケンスです。CPython では動的配列として実装されています。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 直接参照 |
| `access[i]` | O(1) | O(1) | 添字による直接アクセス |
| `append(x)` | 償却 O(1) | 償却 O(1) | リサイズすることがある。再確保が必要な最悪の場合は O(n) |
| `insert(0, x)` | O(n) | O(1) | すべての要素をずらす必要がある |
| `insert(i, x)` | O(n-i) | O(1) | 添字 i 以降の要素をずらす |
| `remove(x)` | O(n) | O(1) | 探索してからずらす必要がある |
| `pop()` | O(1) | O(1) | 末尾の要素を取り除く |
| `pop(0)` | O(n) | O(1) | 残りの要素をずらす |
| `pop(i)` | O(n-i) | O(1) | i より後ろの要素をずらす |
| `clear()` | O(n) | O(1) | メモリを解放する |
| `index(x)` | O(n) | O(1) | 線形探索 |
| `count(x)` | O(n) | O(1) | 線形走査 |
| `sort()` | 平均・最悪 O(n log n)、最良 O(n) | O(n) | Timsort / Powersort、部分的に整列済みのデータに適応する |
| `reverse()` | O(n) | O(1) | その場での反転 |
| `copy()` | O(n) | O(n) | 浅いコピー |
| `extend(iterable)` | O(k) | O(k) | k はイテラブルの長さ。O(n) のリサイズを誘発することがある |
| `in`（メンバーシップ） | O(n) | O(1) | 線形探索 |
| `x + y`（連結） | O(m+n) | O(m+n) | m と n はそれぞれの長さ |
| `[::2]`（スライス） | O(k) | O(k) | k はスライスの長さ |

## 実装の詳細

### 動的配列のリサイズ

CPython のリストは次の成長戦略を使います。

```
If size >= capacity:
    new_capacity = (newsize + newsize // 8 + 6) & ~3  # Aligned to multiple of 4
```

これは次のことを意味します。

- append は償却 O(1) である
- append のたびにリサイズするわけではない
- 多めに確保することでリサイズの頻度が下がる

### append の性能

```python
# O(1) amortized
lst = []
for i in range(1000000):
    lst.append(i)  # Resizes ~log(n) times
```

### insert の性能

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
```

## バージョン別の注記

- **Python 3.8+**: 現在の挙動で安定
- **Python 3.11+**: `append()` が約 15% 高速化、リスト内包表記が 20-30% 高速化
- **Python 3.12+**: 内包表記がインライン化（最大 2 倍高速）
- **すべてのバージョン**: 中心的な計算量は Python 3.x の初期から変わっていない

## 実装ごとの比較

### CPython
動的配列を用いた標準のリファレンス実装。

### PyPy
JIT による最適化のおかげで計算量の特性は同じ。

### Jython
ほぼ同様だが、Java の配列に基づくためリサイズの係数が異なることがある。

## ベストプラクティス

✅ **推奨**:

- 要素の追加には `append()` を使う
- 複数の要素をまとめて追加するには `extend()` を使う
- 先頭に足したい場合は、末尾に追加してから反転する

❌ **避けるべきこと**:

- 頻繁に行う操作としての `insert(0, x)` - 代わりに `collections.deque` を使う
- `pop(0)` の繰り返し - `deque.popleft()` を使う
- `append()` や `extend()` ではなく連結（`+`）で大きなリストを組み立てる

## 関連する型

- **[Deque](../stdlib/collections.md#deque)** - 先頭と末尾への追加が O(1)
- **[配列](../stdlib/array.md)** - 大きな数値のリストではメモリ効率が高い
- **[タプル](tuple.md)** - 不変の代替

## さらに読む

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython のリスト実装を掘り下げた解説
