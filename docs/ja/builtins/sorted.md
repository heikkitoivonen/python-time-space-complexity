---
source_sha: ec504b5b92c746504f94fdd152feeacc24d552795359d63db896da03d453d2ff
translated: machine
---

# sorted() 関数の計算量

`sorted()` 関数は、イテラブルの要素を並べ替えた新しいリストを返します。

## 計算量の分析

| 場合 | 時間 | 空間 | 備考 |
|------|------|-------|-------|
| 基本的なソート | O(n log n) | O(n) | 入力を新しいリストにコピーし、それをその場でソートする |
| キー関数を使う場合 | O(n log n + n*k) | O(n) | k はキー関数の実行時間、キー関数は要素ごとに一度だけ呼び出され、比較は保存したキーで行う |
| 降順のソート | O(n log n) | O(n) | 安定、ソートの前後でリストを反転するので O(n) の追加コスト |
| すでに整列済み | O(n) | O(n) | 最良の場合、入力が 1 つのランになる。逆順に整列済みの入力も同じコスト |

n は要素数。1 回の比較を O(1) と数え、キー自体の大きさは空間計算量に含めない。

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
# Key is computed once per element, then comparisons use the stored keys
words = ["apple", "pie", "cat", "banana"]
result = sorted(words, key=len)  # Sort by length
# ["pie", "cat", "apple", "banana"]

# Sort by last character
result = sorted(words, key=lambda x: x[-1])
# ["banana", "apple", "pie", "cat"]
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

# The same key via the operator module
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
Python sorts with Timsort (through 3.10) or Powersort (3.11+): a merge sort
that starts from the runs already present in the input.
1. Scan for natural runs - ascending, or descending, which are reversed in place
2. Extend short runs to 32-64 elements with binary insertion sort
3. Merge runs - O(n log n) comparisons overall
4. Input that is already one run: O(n) - nothing to merge

Powersort changes the order in which runs are merged, not the bound.
```

### 性能の特性

```python
# Best case - O(n): the input is already one run
numbers = list(range(100000))
result = sorted(numbers)  # n - 1 comparisons

numbers = list(range(100000, 0, -1))  # Reverse sorted
result = sorted(numbers)  # One descending run, also O(n)

# Average and worst case - O(n log n)
import random
numbers = list(range(100000))
random.shuffle(numbers)
result = sorted(numbers)  # O(n log n)
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
# O(n*m + n log n) - n key calls of O(m) each, then O(n log n) comparisons on the stored keys
def expensive_key(x):
    # O(m) - expensive computation, m = x here
    return sum(range(x))

numbers = list(range(1000))
result = sorted(numbers, key=expensive_key)

# Storing the keys pays only when the same keys serve more than one sort
from operator import itemgetter
keyed = [(x, expensive_key(x)) for x in numbers]  # O(n*m), once
ascending = sorted(keyed, key=itemgetter(1))                 # O(n log n)
descending = sorted(keyed, key=itemgetter(1), reverse=True)  # O(n log n), expensive_key not called again
```

### Decorate-Sort-Undecorate (DSU)

```python
# key= is decorate-sort-undecorate done for you: n key calls, then the
# sort compares only the stored keys, never the items themselves
items = [{"name": "b", "rank": 1}, {"name": "a", "rank": 1}]
result = sorted(items, key=lambda d: d["rank"])  # O(n*k + n log n)
# [{'name': 'b', 'rank': 1}, {'name': 'a', 'rank': 1}] - ties keep input order

# Building (key, item) tuples by hand costs the same n key calls, and on a
# tied key the comparison falls through to the items
decorated = [(d["rank"], d) for d in items]
try:
    sorted(decorated)
except TypeError:
    pass  # dicts do not order; key= never compared them
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
# O(L + n log n) - str.lower() costs each word's length, L = total characters
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
import random
numbers = list(range(1000000))
random.shuffle(numbers)

# sorted() - O(n log n), entire list sorted
all_sorted = sorted(numbers)

# heapq.nsmallest() - O(n log k) for k items
import heapq
k_smallest = heapq.nsmallest(10, numbers)  # Wins when k << n
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
# O(n) - one ascending run, n - 1 comparisons
numbers = list(range(1000000))
result = sorted(numbers)
```

### 逆順に整列済み

```python
# O(n) - one descending run, reversed in place
numbers = list(range(1000000, 0, -1))
result = sorted(numbers)
```

## ベストプラクティス

✅ **推奨**:

- 並べ替えた新しいリストを作るには `sorted()` を使う
- 独自の順序には `key` 引数を使う
- `(key, item)` のタプルを自分で組み立てるのではなく `key=` を使う
- 同じキーで何度も並べ替えるなら、コストの高いキーは一度だけ保存しておく

❌ **避けるべきこと**:

- `sorted()` を何度も呼ぶ（結果をキャッシュする）
- 小さいほうから k 個だけ必要なのに入力全体をソートする（`heapq.nsmallest()` を使う）
- キー関数で済むところで `functools.cmp_to_key()` を使う（要素ごとではなく比較ごとに Python の呼び出しが起きる）
- `sorted()` が新しいリストを作ること（メモリを使うこと）を忘れる

## 関連する関数

- **[list.sort()](list.md)** - その場でのソート
- **[heapq.nsmallest()](../stdlib/heapq.md)** - 小さいほうから k 個
- **[heapq.nlargest()](../stdlib/heapq.md)** - 大きいほうから k 個
- **[max()](max.md)** - ソートせずに最大値を求める

## バージョン別の注記

- **Python 2.3-3.10**: Timsort アルゴリズムを使う
- **Python 3.11+**: Powersort を使う（マージ方針が改善されたが、計算量は同じ）
