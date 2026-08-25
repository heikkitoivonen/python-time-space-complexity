---
source_sha: 481ae7e0eb06ad0f4ca7fba108eb1d8b8d8dfb70d13bf0b405746fc83f0d311c
translated: machine
---

# 集合操作の計算量

`set` 型は重複のない要素を順序なしで集めたものです。CPython では辞書と同様のハッシュテーブルとして実装されています。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 保持している個数を返す |
| `add(x)` | 平均 O(1)、最悪 O(n) | 償却 O(1) | ハッシュ衝突があると O(n) になる |
| `remove(x)` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ探索と削除 |
| `discard(x)` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ探索と削除 |
| `pop()` | 平均 O(1) | O(1) | 任意の要素を 1 つ取り除く |
| `clear()` | O(n) | O(1) | すべて解放する |
| `x in set` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ探索、衝突があると O(n) になる |
| `copy()` | O(n) | O(n) | 浅いコピー |
| `union(other)` | O(n+m) | O(n+m) | n と m は集合の大きさ |
| `intersection(other)` | O(min(n,m)) | O(min(n,m)) | 小さいほうの集合を走査する |
| `difference(other)` | O(n) | O(n) | n は集合の大きさ |
| `symmetric_difference(other)` | O(n+m) | O(n+m) | 集合演算の組み合わせ |
| `issubset()` | O(n) | O(1) | すべての要素を調べる |
| `issuperset()` | O(m) | O(1) | m は相手の大きさ |
| `isdisjoint()` | O(min(n,m)) | O(1) | 早期に打ち切る |
| `update(other)` | O(m) | O(1) | その場での和、m = len(other) |
| `difference_update(other)` | O(m) | O(1) | その場での差 |
| `intersection_update(other)` | O(n) | O(1) | その場での積、集合を作り直す |
| `symmetric_difference_update(other)` | O(m) | O(1) | その場での対称差 |

## 実装の詳細

### ハッシュテーブルによる実装

集合は辞書と同じハッシュテーブルの設計を使っていますが、次の違いがあります。

- キーだけを保持する（値は持たない）
- 辞書よりメモリ効率が良い
- 平均 O(1) の探索という点は同じ

### 集合演算

```python
# Union: combines both sets
{1, 2} | {2, 3}  # {1, 2, 3} - O(len(s1) + len(s2))

# Intersection: common elements
{1, 2, 3} & {2, 3, 4}  # {2, 3} - O(min(len(s1), len(s2)))

# Difference: elements in first but not second
{1, 2, 3} - {2, 4}  # {1, 3} - O(len(s1))

# Symmetric difference: elements in either but not both
{1, 2} ^ {2, 3}  # {1, 3} - O(len(s1) + len(s2))
```

### メンバーシップの判定

```python
# Very fast - O(1) hash lookup
s = {1, 2, 3, 4, 5}
if 3 in s:  # O(1), not O(n)
    pass
```

## リストとの比較

```python
# List membership: O(n) - must scan entire list
numbers_list = [1, 2, 3, 4, 5]
3 in numbers_list  # O(n)

# Set membership: O(1) - hash lookup
numbers_set = {1, 2, 3, 4, 5}
3 in numbers_set  # O(1) - much faster for large collections!
```

## バージョン別の注記

- **Python 3 のすべてのバージョン**: 中心的な計算量は変わっていない
- **Python 3.9+**: 新しい集合の和・積の演算子

## 実装ごとの比較

### CPython
標準的なハッシュテーブル実装。

### PyPy
JIT コンパイルによりさらに最適化される場合がある。

### Jython
下層で Java の HashSet を使うが、O(1) という特性は同じ。

## ベストプラクティス

✅ **推奨**:

- 大きなコレクションでのメンバーシップ判定には集合を使う
- 集合を組み合わせるには集合演算（`|`、`&`、`-`、`^`）を使う
- 重複を取り除くのに集合を使う: `set(list_with_dups)`
- ハッシュ可能で重複のない要素には `frozenset` を使う

❌ **避けるべきこと**:

- 頻繁なメンバーシップ判定にリストを使う
- 集合の順序に頼る（保証されていない）
- ハッシュ不可能な型（リスト、辞書）を集合に入れる

## よくあるパターン

### 重複の除去

```python
# Bad: preserves list, but O(n²)
unique = []
for item in items:
    if item not in unique:
        unique.append(item)

# Good: O(n), but loses order
unique = list(set(items))

# Best: O(n) and preserves order (Python 3.7+)
unique = list(dict.fromkeys(items))
```

### 高速な絞り込み

```python
# Bad: O(n*m) - checks membership in list for each element
large_list = list(range(1000000))
exclusions = [1, 2, 3, ...]
filtered = [x for x in large_list if x not in exclusions]

# Good: O(n) - fast set lookup
exclusions_set = set(exclusions)
filtered = [x for x in large_list if x not in exclusions_set]
```

## 関連する型

- **[Frozenset](index.md)** - 不変の集合
- **[Dict](dict.md)** - 可変のマッピング
- **[Deque](../stdlib/collections.md#deque)** - 順序を持つコレクション

## さらに読む

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython の集合実装を掘り下げた解説
