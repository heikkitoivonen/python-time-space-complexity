---
source_sha: 699f54d0f15380f0acf2cc37e53cc5f55cb222c850ade1649086deaeb841be2c
translated: machine
---

# 標準ライブラリの計算量

Python の標準ライブラリは、よくある作業のために高度に最適化されたデータ構造とアルゴリズムを提供しています。

## 中心的なコレクション

- **[Collections](collections.md)** - `deque`、`namedtuple`、`defaultdict`、`OrderedDict`、`ChainMap`、`Counter`
- **[Itertools](itertools.md)** - 効率的なループとイテレータの道具
- **[Heapq](heapq.md)** - ヒープキューの操作
- **[Bisect](bisect.md)** - 二分探索と挿入

## 関数型と便利な道具

- **[Functools](functools.md)** - 高階関数とメモ化
- **[JSON](json.md)** - JSON のシリアライズと解析

## 探索とソート

| モジュール | 用途 | 時間 |
|--------|---------|------|
| `bisect` | 整列済みリストの二分探索 | O(log n) |
| `heapq` | ヒープの操作 | O(log n) |
| `sorted()` | 任意のイテラブルのソート | O(n log n) |

## よく使うもの

### collections モジュール

```python
from collections import deque, defaultdict, Counter

# deque: Fast append/prepend
d = deque([1, 2, 3])
d.appendleft(0)  # O(1)

# defaultdict: Auto-default values
d = defaultdict(list)
d[key].append(value)  # Key created if missing

# Counter: Count items
c = Counter(['a', 'a', 'b'])
c['a']  # Returns 2
```

### heapq モジュール

```python
import heapq

# Min heap operations
heap = [3, 1, 4, 1, 5]
heapq.heapify(heap)  # O(n)
heapq.heappop(heap)  # O(log n)
heapq.heappush(heap, 2)  # O(log n)
```

### bisect モジュール

```python
import bisect

# Binary search in sorted lists
arr = [1, 3, 3, 3, 5]
bisect.bisect_left(arr, 3)  # O(log n)
bisect.insort(arr, 4)  # O(n) - must shift
```

## データ構造のクイックリファレンス

| 型 | 末尾へ追加 | 先頭へ追加 | アクセス | 包含判定 |
|------|--------|---------|--------|----------|
| list | O(1)* | O(n) | O(1) | O(n) |
| deque | O(1) | O(1) | O(n) | O(n) |
| heapq | O(log n) | - | 最小値は O(1) | O(n) |
| set | - | - | - | O(1) |
| dict | - | - | O(1) | O(1) |

## バージョンの要点

- **Python 3.7+**: `dict` の挿入順序が保たれる
- **Python 3.8+**: 代入式（ウォルラス演算子）
- **Python 3.10+**: データクラスに対するパターンマッチング

## 関連項目

- [組み込み](../builtins/index.md)
- [実装](../implementations/index.md)
