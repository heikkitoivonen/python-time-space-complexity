---
source_sha: 5cc0baa48e47524cffa1ac98fc48d08ce288f6b12b9c606be0900034949724d0
translated: machine
---

# sorted() 関数の計算量

`sorted()` 関数は、イテラブルの要素を並べ替えた新しいリストを返します。

## 計算量の分析

| 場合 | 時間 | 空間 | 備考 |
|------|------|-------|-------|
| 基本的なソート | O(n log n) | O(n) | Timsort / Powersort |
| キー関数を使う場合 | O(n log n + n*k) | O(n) | k はキー関数の実行時間、キーは要素ごとに一度だけ計算される |
| 降順のソート | O(n log n) | O(n) | 追加のコストはない |
| すでに整列済み | O(n) | O(n) | 最良の場合 |

## 基本的な使い方

### 単純なソート

```python
# O(n log n) - Timsort (≤3.10) or Powersort (3.11+)
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
result = sorted(numbers)
# [1, 1, 2, 3, 4, 5, 6, 9]

# Works with any iterable
result = sorted((3, 1, 4))  # Tuple input
# [1, 3, 4]

result = sorted({3, 1, 4})  # Set input
# [1, 3, 4]

result = sorted("cadb")     # String input
# ['a', 'b', 'c', 'd']
```

### 降順のソート

```python
# O(n log n) - same complexity
numbers = [3, 1, 4, 1, 5, 9, 2, 6]
result = sorted(numbers, reverse=True)
# [9, 6, 5, 4, 3, 2, 1, 1]

# Works with strings
words = ["apple", "pie", "cat"]
result = sorted(words, reverse=True)
# ["pie", "cat", "apple"]
```

## キー関数を使う

### 独自の比較

```python
# O(n log n + n*k) where k = key function time
# Key is computed once per element, then comparisons use cached keys
words = ["apple", "pie", "cat", "banana"]
result = sorted(words, key=len)  # Sort by length
# ["pie", "cat", "apple", "banana"]

# Sort by last character
result = sorted(words, key=lambda x: x[-1])
# ["apple", "banana", "pie", "cat"]
```

### オブジェクトのソート

```python
# O(n log n) - simple key extraction
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
    
    def __repr__(self):
        return f"Person({self.name}, {self.age})"

people = [
    Person("Alice", 30),
    Person("Bob", 25),
    Person("Charlie", 35),
]

# Sort by age
result = sorted(people, key=lambda p: p.age)
# [Person(Bob, 25), Person(Alice, 30), Person(Charlie, 35)]

# Using operator module (more efficient)
from operator import attrgetter
result = sorted(people, key=attrgetter('age'))  # Same O(n log n)
```

### タプルのソート

```python
# O(n log n) - lexicographic comparison
coords = [(1, 5), (3, 2), (2, 8)]
result = sorted(coords)
# [(1, 5), (2, 8), (3, 2)]

# Sort by second element
result = sorted(coords, key=lambda c: c[1])
# [(3, 2), (1, 5), (2, 8)]
```

## ソートアルゴリズム

### 仕組み

```
Python uses Timsort (Python 2.3-3.10) or Powersort (Python 3.11+).
Both are hybrid algorithms combining merge sort and insertion sort:
1. Divide array into small chunks (runs) - ~32-64 elements
2. Sort each run with insertion sort - O(k²) per run
3. Merge runs together - O(n log n) overall
4. Already sorted data: O(n) - detects and uses it

Powersort uses an improved merge policy but has the same complexity.
```

### 性能の特性

```python
# Best case - O(n) - already sorted or reverse sorted
numbers = list(range(1000000))
result = sorted(numbers)  # Nearly O(n) for nearly sorted data

# Average case - O(n log n)
import random
numbers = list(range(1000))
random.shuffle(numbers)
result = sorted(numbers)  # O(n log n)

# Worst case - O(n log n) - still guaranteed
numbers = [1000 - i for i in range(1000)]  # Reverse sorted
result = sorted(numbers)  # O(n log n) - handles well
```

## 性能に関するパターン

### sorted() と sort()

```python
# sorted() - creates new list, O(n log n) time, O(n) space
original = [3, 1, 4, 1, 5]
result = sorted(original)  # [1, 1, 3, 4, 5]
# original unchanged

# list.sort() - in-place, O(n log n) time, O(n) space
original = [3, 1, 4, 1, 5]
original.sort()  # [1, 1, 3, 4, 5]
# original modified

# Both use same algorithm, same complexity but sorted() makes copy
```

### コストの高いキー関数

```python
# O(n*k + n log n) - key computed once per element, then cached
def expensive_key(x):
    # O(m) - expensive computation
    return sum(range(x))

numbers = list(range(1000))
result = sorted(numbers, key=expensive_key)
# Complexity: O(n*m + n log n) - key called n times, then n log n comparisons

# Better: pre-compute keys
from operator import itemgetter
keys = [(x, expensive_key(x)) for x in numbers]  # O(n*m)
result = sorted(keys, key=itemgetter(1))         # O(n log n)
# Total: O(n*m + n log n)
```

### Decorate-Sort-Undecorate (DSU)

```python
# O(n log n) - when computing key is expensive
def get_sort_key(item):
    # Some expensive computation
    return complex_calculation(item)

# With key: O(n*k + n log n) - key computed once per element
result = sorted(items, key=get_sort_key)

# Faster: O(n*k + n log n)
decorated = [(get_sort_key(item), item) for item in items]  # O(n*k)
sorted_decorated = sorted(decorated)                          # O(n log n)
result = [item for _, item in sorted_decorated]              # O(n)
```

## ソートの安定性

```python
# sorted() is stable - preserves order of equal elements
data = [(1, 'a'), (2, 'b'), (1, 'c'), (2, 'd')]
result = sorted(data, key=lambda x: x[0])
# [(1, 'a'), (1, 'c'), (2, 'b'), (2, 'd')]
# Among equal keys, original order preserved
```

## よくあるパターン

### 複数のソート基準

```python
# Sort by multiple attributes - O(n log n)
students = [
    ('Alice', 85),
    ('Bob', 85),
    ('Charlie', 90),
]

# Sort by score descending, then name ascending
result = sorted(students, key=lambda s: (-s[1], s[0]))
# [('Charlie', 90), ('Alice', 85), ('Bob', 85)]
```

### 大文字小文字を無視したソート

```python
# O(n log n) - with case conversion
words = ["Apple", "banana", "Cherry", "date"]
result = sorted(words, key=str.lower)
# ["Apple", "banana", "Cherry", "date"]
```

### 独自の順序でのソート

```python
# O(n log n) - custom comparison key
priority = {'high': 0, 'medium': 1, 'low': 2}
tasks = [
    {'name': 'A', 'priority': 'low'},
    {'name': 'B', 'priority': 'high'},
    {'name': 'C', 'priority': 'medium'},
]

result = sorted(tasks, key=lambda t: priority[t['priority']])
# B (high), C (medium), A (low)
```

## ほかのソート手段との比較

### sorted() と list.sort()

```python
# sorted() - returns new list, original unchanged
original = [3, 1, 4, 1, 5]
result = sorted(original)

# list.sort() - modifies in-place, returns None
original = [3, 1, 4, 1, 5]
original.sort()

# Both: O(n log n) time, O(n) space for Timsort/Powersort
# Choose based on whether you need original
```

### sorted() と heapq.nsmallest()

```python
# sorted() - O(n log n), entire list sorted
numbers = list(range(1000000))
all_sorted = sorted(numbers)

# heapq.nsmallest() - O(n log k) for k items
import heapq
k_smallest = heapq.nsmallest(10, numbers)  # Much faster if k << n
```

## 端の場合

### 空のリスト

```python
# O(1) - no sorting needed
result = sorted([])
# []
```

### 要素が 1 つ

```python
# O(1) - nothing to sort
result = sorted([42])
# [42]
```

### すでに整列済み

```python
# O(n) - Timsort/Powersort detects and handles efficiently
numbers = list(range(1000000))
result = sorted(numbers)  # Nearly O(n)
```

### 逆順に整列済み

```python
# O(n) - also handled efficiently
numbers = list(range(1000000, 0, -1))
result = sorted(numbers)  # Nearly O(n)
```

## ベストプラクティス

✅ **推奨**:

- 並べ替えた新しいリストを作るには `sorted()` を使う
- 独自の順序には `key` 引数を使う
- 属性で並べ替えるときは lambda ではなく `operator.attrgetter()` を使う
- 同じキーで何度も並べ替えるなら、コストの高いキーは事前に計算しておく

❌ **避けるべきこと**:

- `sorted()` を何度も呼ぶ（結果をキャッシュする）
- 複雑な lambda 関数（代わりに関数を定義する）
- キーの中でコストの高い計算をして並べ替える（事前に計算する）
- `sorted()` が新しいリストを作ること（メモリを使うこと）を忘れる

## 関連する関数

- **[list.sort()](list.md)** - その場でのソート
- **[heapq.nsmallest()](../stdlib/heapq.md)** - 小さいほうから k 個
- **[heapq.nlargest()](../stdlib/heapq.md)** - 大きいほうから k 個
- **[max()](max.md)** - ソートせずに最大値を求める

## バージョン別の注記

- **Python 2.3-3.10**: Timsort アルゴリズムを使う
- **Python 3.11+**: Powersort を使う（マージ方針が改善されたが、計算量は同じ）
