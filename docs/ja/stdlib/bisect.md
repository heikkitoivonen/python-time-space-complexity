---
source_sha: a94d3e8a9450b59cb245eb0f1ed57d4adf9f9336e3b33dadbbff5a31abbd09b2
translated: machine
---

# bisect モジュールの計算量

`bisect` モジュールは、呼び出し側がソート済みに保っているシーケンスの中で位置を求めます。ソートも
順序の検査も一切行いません。各探索は与えられた範囲を半分にしながら、1 ステップごとに要素を 1 つ
読み、追加のメモリは定数です。挿入関数はこの探索とシーケンス自身の `insert()` を組み合わせたもので、
リストではコストがかかるのは探索ではなく挿入のほうです。

`n` はシーケンスの長さです。探索の上界はプローブ数で数えます。1 回のプローブは要素の読み取り 1 回、
キー関数が指定されていれば `key` の呼び出し 1 回、そして `<` の比較 1 回からなり、いずれも O(1)
とみなします。より重い処理を行うキー関数や比較は、そのコストの分だけ探索を重くします。添字アクセスは
リストと同じく O(1) です。ここで 2 つの要素が等しいとは、どちらも他方に対して `<` でないことを
指し、`key` が指定されていればキー同士を比較します。

## 計算量リファレンス

### 探索

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `bisect.bisect_left(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | `x` と等しい要素の並びの手前の位置。`key` はプローブした各要素に適用され、`x` には適用されません |
| `bisect.bisect_right(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | `x` と等しい要素の並びの直後の位置 |
| `bisect.bisect(a, x, lo=0, hi=len(a), *, key=None)` | O(log n) | O(1) | `bisect_right` と同じ関数 |

### 挿入

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `bisect.insort_left(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | O(log n) の探索のあと `a.insert()` を呼び、リストでは後続の要素がずれます。`key` は `x` に 1 回適用されます |
| `bisect.insort_right(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | `x` と等しい要素の並びの直後に挿入します |
| `bisect.insort(a, x, lo=0, hi=len(a), *, key=None)` | O(n) | O(1) | `insort_right` と同じ関数 |

## ソート済みリストの探索

### 左と右

2 つの探索の違いは、等しい要素の並びに対してどこに着地するかだけです。`bisect_left` は並びの手前、
`bisect_right` は並びの直後です。どちらも範囲を半分にしていくので、重複の並びの探索もほかの探索と
同じく O(log n) で、2 つを組み合わせれば並びの長さにかかわらずその両端を求められます。

```python
import bisect

values = [1, 3, 3, 3, 5, 7, 9]

left = bisect.bisect_left(values, 3)    # O(log n)
right = bisect.bisect_right(values, 3)  # O(log n)
assert (left, right) == (1, 4)
assert values[left:right] == [3, 3, 3]
assert right - left == 3                # occurrences counted without a scan

def contains(sorted_list, x):
    i = bisect.bisect_left(sorted_list, x)  # O(log n), against O(n) for `x in sorted_list`
    return i < len(sorted_list) and sorted_list[i] == x

assert contains(values, 5)
assert not contains(values, 4)
```

### lo と hi による絞り込み

`lo` と `hi` は探索するスライスを区切り、探索のコストはシーケンスの長さにかかわらず
O(log(hi - lo)) です。ただし `insort` はリスト全体に対する挿入のコストを払います。負の `lo` は
`ValueError` を送出します。

```python
import bisect

values = list(range(0, 1_000, 2))

assert bisect.bisect_left(values, 100, lo=40, hi=60) == 50  # O(log 20)

try:
    bisect.bisect_left(values, 100, lo=-1)
except ValueError as error:
    assert 'lo must be non-negative' in str(error)
else:
    raise AssertionError('a negative lo was accepted')
```

### キーによる探索

`key` はプローブごとに 1 回、プローブした要素に対して呼ばれるので、キー付きの探索は O(log n) 回の
キー呼び出しで済み、並行するリストは不要です。`x` に対しては呼ばれません。探索関数は `x` をすでに
キーの値として受け取ります。例外は `insort` で、レコードそのものを挿入するため、位置を求めるのに
`key(x)` を 1 回呼びます。

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
by_count = lambda record: record[1]

pos = bisect.bisect_right(records, 4, key=by_count)  # O(log n) key calls; x is the key value
assert pos == 2

bisect.insort(records, ('d', 4), key=by_count)  # O(n); key(x) is called here
assert records == [('a', 1), ('b', 3), ('d', 4), ('c', 5)]
```

多くの探索が 1 つのリストを共有する場合は、キーの並行リストという選択肢もあります。構築に O(n)
かかり、挿入のたびに同期させる必要がありますが、その後の探索ではキー呼び出しが発生しません。

```python
import bisect

records = [('a', 1), ('b', 3), ('c', 5)]
keys = [record[1] for record in records]  # O(n) once

pos = bisect.bisect_right(keys, 4)  # O(log n), no key calls
records.insert(pos, ('d', 4))       # O(n)
keys.insert(pos, 4)                 # O(n) - keys must follow every insert
assert keys == [record[1] for record in records] == [1, 3, 4, 5]
```

### ソートされていない入力

スライスがソート済みかどうかは何も検査されません。ソートされていない入力でも探索は例外を送出せずに
位置を返しますが、それが正しい位置である保証はなく、そこに挿入した後もリストがソートされていない
ことがあります。

```python
import bisect

unsorted = [3, 1, 4, 1, 5]

pos = bisect.bisect(unsorted, 2)  # O(log n), no error
result = unsorted[:pos] + [2] + unsorted[pos:]
assert result != sorted(result)
```

## リストをソート済みに保つ

### 1 件ずつの挿入とまとめての挿入

リストへの `insort` は 1 回ごとに O(n) なので、n 要素のリストへの k 回の挿入は O(k·(n + k))
かかります。挿入がまとめて届き、その間に探索がない場合は、末尾に追加して 1 回ソートすれば
O((n + k) log(n + k)) で済みます。探索と挿入が交互に起こる場合は `insort` が適しています。

```python
import bisect

values = [1, 3, 5, 7]
bisect.insort(values, 4)  # O(n) - the tail shifts
assert values == [1, 3, 4, 5, 7]

# Many inserts at once: O(k·(n + k)) one at a time
one_at_a_time = [1, 3, 5, 7, 9]
for item in [8, 2, 6, 4]:
    bisect.insort(one_at_a_time, item)  # O(n) each

# ... or O((n + k) log(n + k)) as one sort
batch = [1, 3, 5, 7, 9]
batch.extend([8, 2, 6, 4])
batch.sort()
assert batch == one_at_a_time
```

## よくあるパターン

### 点数を区分に対応づける

```python
import bisect

breakpoints = [60, 70, 80, 90]
grades = 'FDCBA'

def grade(score):
    return grades[bisect.bisect(breakpoints, score)]  # O(log b), b = breakpoints

assert [grade(score) for score in (33, 60, 77, 89, 90, 100)] == list('FDCBAA')
```

### 時間範囲内のイベント

```python
import bisect
from datetime import datetime

events = [
    (datetime(2024, 1, 1, 10), 'event1'),
    (datetime(2024, 1, 1, 12), 'event2'),
    (datetime(2024, 1, 1, 15), 'event3'),
    (datetime(2024, 1, 1, 18), 'event4'),
]
when = lambda event: event[0]

start = bisect.bisect_left(events, datetime(2024, 1, 1, 11), key=when)  # O(log n)
end = bisect.bisect_right(events, datetime(2024, 1, 1, 15), key=when)   # O(log n)
assert [name for _, name in events[start:end]] == ['event2', 'event3']  # O(m), m = matches
```

## 性能のベストプラクティス

✅ **推奨**:

- ソート済みリストの所属判定には、O(n) の `in` ではなく `bisect_left` と比較 1 回を使う
- 等しい要素の並びを数えるには `bisect_right - bisect_left` を使い、O(log n) で求める
- 答えがリストの一部にあるとわかっているときは `lo` と `hi` を渡す
- レコードをたまに探索するなら `key` を使い、多くの探索で共有するならキーの並行リストを保持する

❌ **避ける**:

- 1 回の探索のためにキーのリストを作る - O(log n) の答えのために O(n) を払うことになる
- まとまったデータを `insort` の繰り返しでリストに入れる - 末尾に追加して 1 回ソートする
- ソート済みに保っていないリストを探索する - 答えは信頼できず、例外も送出されない

## バージョン別の注記

- **Python 3.10+**: 6 つの関数すべてに `key` 引数が追加されました

## 関連モジュール

- **[heapq](heapq.md)** - ソート済みリストではなく最小の要素だけが必要なときの O(log n) の
  push と pop
- **[list](../builtins/list.md)** - `insort` とまとめてのソートが依拠する `insert()` と
  `sort()` のコスト
