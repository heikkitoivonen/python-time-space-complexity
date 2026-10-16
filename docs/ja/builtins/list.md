---
source_sha: 4be9c7effa33db1176d1ac0933f57739a43404edc602043c8eb1ae684c37985d
translated: machine
---

# リスト操作の計算量

`list` 型は可変で順序を持つシーケンスです。CPython では動的配列として実装されています。

`n` はリストの長さ、`k` は添字または繰り返し回数、`i:j` はスライスの範囲、`len(t)` はもう一方のオペランドの長さです。要素 2 つの比較は O(1) とみなします。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | 長さはリストに格納されており、数え直さない |
| `l[k]` | O(1) | O(1) | 添字による直接アクセス |
| `l[k] = x` | O(1) | O(1) | 1 つのスロットを置き換える |
| `del l[k]` | O(n-k) | O(1) | k より後ろの要素を 1 つ左へずらす |
| `append(x)` | 償却 O(1) | 償却 O(1) | リサイズすることがある。再確保が必要な最悪の場合は O(n) |
| `insert(0, x)` | O(n) | 償却 O(1) | すべての要素をずらす必要がある |
| `insert(k, x)` | 償却 O(n-k) | 償却 O(1) | 添字 k 以降の要素を 1 つ右へずらす |
| `remove(x)` | O(n) | O(1) | 探索してからずらす必要がある |
| `pop()` | 償却 O(1) | O(1) | 末尾の要素を取り除く。何もずらさない |
| `pop(0)` | O(n) | O(1) | 残りの要素をずらす |
| `pop(k)` | 償却 O(n-k) | O(1) | k より後ろの要素を 1 つ左へずらす |
| `clear()` | O(n) | O(1) | メモリを解放する |
| `index(x)` | O(n) | O(1) | 線形探索 |
| `count(x)` | O(n) | O(1) | 線形走査 |
| `sort()` | 最悪 O(n log n)、整列済みまたは逆順に整列済みの入力では O(n) | O(n) | Timsort / Powersort。適応的なので、すでに整列している部分列は比較回数が少ない |
| `reverse()` | O(n) | O(1) | その場での反転 |
| `copy()` | O(n) | O(n) | 浅いコピー |
| `extend(t)` | 償却 O(len(t)) | O(len(t)) | これに t の反復コストが加わる。O(n) のリサイズを誘発することがある |
| `l[i:j]`（スライス） | O(j-i) | O(j-i) | ステップ付きでは O(結果の長さ) |
| `l[i:j] = t` | len(t) == j-i なら O(j-i)、それ以外は償却 O(n-i+len(t)) | O(j-i+len(t)) | 長さが等しければその場で上書きする。そうでなければ j 以降がすべて移動する |
| `del l[i:j]` | O(n-i) | O(j-i) | j 以降がすべて左へ移動する |
| `l1 + l2`（連結） | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | 新しいリスト |
| `l * k`（繰り返し） | O(nk) | O(nk) | n·k 個の参照を持つ新しいリスト |
| `for x in l`（反復） | O(n) | O(1) | 1 ステップあたり O(1) |
| `x in l`（メンバーシップ） | O(n) | O(1) | 線形探索 |
| `min(l)`, `max(l)` | O(n) | O(1) | 比較は n-1 回 |

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
assert len(lst) == 1000000
```

### insert の性能

```python
# O(n) - must shift all elements after insertion point
lst = [0] * 1000000
lst.insert(0, -1)  # Shifts 1,000,000 elements!
assert lst[0] == -1 and len(lst) == 1000001
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
