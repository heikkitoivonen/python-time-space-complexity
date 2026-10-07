---
source_sha: bc027a0b06cdd8740a2521704ec5280e0839aa5d5e037704f37c0fb6913b975e
translated: machine
---

# heapq モジュールの計算量

`heapq` モジュールは、通常の `list` の中に二分ヒープを保持します。ヒープ型は存在せず、あるのは
自分が所有するリストの中で要素を移動させ、`heap[0]` が常に最小になるようにする関数だけです。
すべての操作はインプレースで行われ、独自に何かを保持するのは `nlargest`、`nsmallest`、`merge`
だけです。

`n` はヒープ内の要素数、`m` は入力のイテラブルから取り出される要素数、`k` は `nlargest` または
`nsmallest` に求める要素数、`r` は `merge` に渡すイテラブルの数です。どの上界も要素どうしの比較
回数を数え、1 回の比較と `key` 関数の 1 回の呼び出しを O(1) として扱います。

## 計算量リファレンス

### 最小ヒープの関数

| 操作 | 時間 | 空間 | 備考 |
|------|------|------|------|
| `heapq.heapify(x)` | O(n) | O(1) | インプレース |
| `heapq.heappush(heap, item)` | 償却 O(log n) | 償却 O(1) | リストは `append` と同じように伸長する |
| `heapq.heappop(heap)` | 償却 O(log n) | O(1) | リストは `pop` と同じように縮小する。空のヒープでは `IndexError` を送出する |
| `heapq.heappushpop(heap, item)` | O(log n) | O(1) | ヒープが空か、`item` が `heap[0]` より大きくないときは、ヒープに触れず O(1) |
| `heapq.heapreplace(heap, item)` | O(log n) | O(1) | 追加より先に取り出すため、`item` より大きい要素を返すことがある。空のヒープでは `IndexError` を送出する |
| `heap[0]` の読み取り | O(1) | O(1) | 取り除かずに最小の要素を得る |

### 最大ヒープの関数

| 操作 | 時間 | 空間 | 備考 |
|------|------|------|------|
| `heapq.heapify_max(x)` | O(n) | O(1) | Python 3.14+。その後 `heap[0]` は最大の要素になる |
| `heapq.heappush_max(heap, item)` | 償却 O(log n) | 償却 O(1) | Python 3.14+ |
| `heapq.heappop_max(heap)` | 償却 O(log n) | O(1) | Python 3.14+。空のヒープでは `IndexError` を送出する |
| `heapq.heappushpop_max(heap, item)` | O(log n) | O(1) | Python 3.14+。ヒープが空か、`item` が `heap[0]` より小さくないときは、ヒープに触れず O(1) |
| `heapq.heapreplace_max(heap, item)` | O(log n) | O(1) | Python 3.14+。空のヒープでは `IndexError` を送出する |

### 選択とマージ

| 操作 | 時間 | 空間 | 備考 |
|------|------|------|------|
| `heapq.nlargest(k, iterable, key=None)` | O(m log k) | O(k) | 結果に入れない要素は比較 1 回で済むため、k が小さいランダムな入力ではほぼ O(m)。昇順の入力ではすべての要素が結果に入る。k = 1 は `max()` による 1 回の走査で O(m)。`key` は要素ごとに 1 回呼ばれる |
| `heapq.nsmallest(k, iterable, key=None)` | O(m log k) | O(k) | 鏡像の関係: 降順の入力が最悪ケースで、k = 1 は `min()` による 1 回の走査 |
| `heapq.merge(*iterables, key=None, reverse=False)` | O(r + m log r) | O(r) | 遅延評価: 入力ごとに 1 要素だけを保持する。各入力は出力と同じ向きにソート済みでなければならず、それは検査されない。`key` は要素ごとに高々 1 回呼ばれる |

## ヒープの構造

ヒープとは、位置 `i` の要素が `2*i + 1` と `2*i + 2` にある 2 つの要素より大きくないリストです。
`heapify` が O(n) で確立するのはそれだけです。リストはソートされておらず、最小だとわかっているのは
`heap[0]` だけです。

```python
import heapq

data = [5, 3, 7, 1, 9, 4]
heapq.heapify(data)  # O(n), in place

assert data[0] == 1          # O(1) - the root is the smallest
assert data != sorted(data)  # a heap, not a sorted list
for parent in range(len(data)):
    for child in (2 * parent + 1, 2 * parent + 2):
        if child < len(data):
            assert data[parent] <= data[child]
```

## 追加と取り出し

追加や取り出しは根と葉の間の経路を 1 本たどるので、コストはヒープの高さ、つまり O(log n) です。
したがってヒープ全体を取り出し尽くすと O(n log n) になります。

```python
import heapq

heap = []
for priority in [5, 1, 4, 2, 3]:
    heapq.heappush(heap, priority)  # O(log n) amortized

assert heap[0] == 1  # O(1) peek
drained = [heapq.heappop(heap) for _ in range(len(heap))]  # O(n log n) in total
assert drained == [1, 2, 3, 4, 5]

try:
    heapq.heappop(heap)
except IndexError as error:
    assert 'index out of range' in str(error)
else:
    raise AssertionError('popped from an empty heap')
```

### 同順位と比較できないペイロード

タプルはフィールドごとに比較されるため、優先度が等しい 2 つのエントリは次のフィールドの比較に
進みます。そこに一意なカウンタを置けばペイロードは決して比較されません。優先度が等しいものは挿入
順に出てきて、`<` をサポートしないペイロードが比較を求められることもありません。

```python
import heapq
import itertools

class Job:
    def __init__(self, name):
        self.name = name

heap = []
try:
    heapq.heappush(heap, (1, Job('a')))
    heapq.heappush(heap, (1, Job('b')))  # equal priority reaches Job < Job
except TypeError as error:
    assert "'<' not supported" in str(error)
else:
    raise AssertionError('two Jobs were compared')

counter = itertools.count()
heap = []
for name in ['a', 'b', 'c']:
    heapq.heappush(heap, (1, next(counter), Job(name)))  # O(log n)

assert [heapq.heappop(heap)[2].name for _ in range(3)] == ['a', 'b', 'c']
```

## 追加と取り出しの組み合わせ

`heappushpop` と `heapreplace` は、追加と取り出しを 1 回の呼び出しで行い、ヒープのサイズを変え
ません。違いは順序です。`heappushpop` は先に追加するので、根より大きくない要素は 1 回の比較の後
そのまま返されます。`heapreplace` は先に取り出すので、新しい要素より大きい場合でも常に古い根を
返します。

```python
import heapq

heap = [2, 4, 6]
heapq.heapify(heap)

assert heapq.heappushpop(heap, 1) == 1  # O(1) here - 1 never enters the heap
assert heap == [2, 4, 6]

assert heapq.heapreplace(heap, 1) == 2  # O(log n) - pops 2, then pushes 1
assert sorted(heap) == [1, 4, 6]

assert heapq.heappushpop([], 7) == 7  # an empty heap returns the item
```

## 上位 k 個の選択

k が 1 より大きいとき、`nlargest` はそれまでに見た上位 k 個をヒープに保持し、新しい要素をその中で
最も弱いものと比較します。入れない要素のコストはその比較 1 回なので、k が小さいランダムな入力では
ヒープにほとんど触れません。入る要素のコストは O(log k) です。すでに昇順に並んだ入力は
`nlargest` の最悪ケースで、各要素がそれ以前のすべてに勝ちます。降順の入力は `nsmallest` の
最悪ケースです。いずれにせよ k 個を保持する 1 回の走査であり、m 個すべてを保持する `sorted()`
とは対照的です。

```python
import heapq

scores = [31, 7, 88, 54, 12, 99, 63, 5]

assert heapq.nlargest(3, scores) == [99, 88, 63]  # O(m log k), O(k) memory
assert heapq.nsmallest(2, scores) == [5, 7]       # O(m log k)
assert heapq.nlargest(3, scores) == sorted(scores, reverse=True)[:3]  # same answer, O(m log m)

# key is called once per item, and the items themselves are returned
words = ['pear', 'fig', 'banana', 'kiwi']
assert heapq.nlargest(2, words, key=len) == ['banana', 'pear']

# The input can be any iterable, consumed in one pass
assert heapq.nsmallest(2, (x * x for x in range(-3, 4))) == [0, 1]
```

## ソート済み入力のマージ

`merge` はジェネレータです。最初の `next()` で各入力から 1 要素ずつ取り出してヒープ化し、これが
O(r) です。それ以降は、生成する要素ごとに、その入力の次の要素を取り込むための O(log r) の
ふるい分けが高々 1 回かかります。入力ごとに 1 要素より先は読み込まないため、メモリに収まらない
入力もマージできますが、与えられた順序を信用します。ソートされていない入力は、エラーなしに
ソートされていない出力を生みます。

```python
import heapq

merged = heapq.merge([1, 4, 7], [2, 5, 8], [3, 6, 9])  # O(1) - nothing is read yet
assert next(merged) == 1                               # O(r) - one item from each input
assert list(merged) == [2, 3, 4, 5, 6, 7, 8, 9]        # O(log r) per item

# key and reverse: each input must already be sorted that way
by_length = heapq.merge(['fig', 'pear'], ['kiwi', 'banana'], key=len)
assert list(by_length) == ['fig', 'pear', 'kiwi', 'banana']
descending = heapq.merge([9, 5, 1], [8, 2], reverse=True)
assert list(descending) == [9, 8, 5, 2, 1]

# Unsorted input is not detected
assert list(heapq.merge([3, 1], [2])) == [2, 3, 1]
```

## 最大ヒープ

### 最大ヒープの関数

Python 3.14 では 5 つのヒープ関数それぞれに `_max` 版が加わりました。コストは最小ヒープの関数と
同じで、`heap[0]` が最小ではなく最大の要素になります。

```python
import heapq

data = [3, 1, 4, 1, 5, 9, 2, 6]
heapq.heapify_max(data)  # O(n)
assert data[0] == 9      # O(1) - the root is the largest

heapq.heappush_max(data, 10)          # O(log n) amortized
assert heapq.heappop_max(data) == 10  # O(log n) amortized

assert heapq.heapreplace_max(data, 7) == 9   # O(log n) - pops 9, then pushes 7
assert heapq.heappushpop_max(data, 8) == 8   # O(1) here - 8 is not smaller than the root
assert data[0] == 7
```

### Python 3.14 より前

数値の優先度を符号反転すれば、同じコストで最小ヒープの関数を最大ヒープとして使えます。

```python
import heapq

data = [3, 1, 4, 1, 5]
max_heap = [-x for x in data]  # O(n)
heapq.heapify(max_heap)        # O(n)

assert -max_heap[0] == 5               # O(1) peek
assert -heapq.heappop(max_heap) == 5   # O(log n)
heapq.heappush(max_heap, -9)           # O(log n)
assert -max_heap[0] == 9
```

## よくあるパターン

### ストリームに対する上限付きの上位 k 個

要素が 1 つずつ届き、上位 k 個だけが重要なときは、k 要素の最小ヒープでそれらを保持できます。根は
残っている中で最も弱いもので、`heappushpop` は新しい要素がそれに勝つときだけ置き換えます。

```python
import heapq

k = 3
best = []
for reading in [12, 40, 7, 33, 51, 8, 29, 60]:
    if len(best) < k:
        heapq.heappush(best, reading)      # O(log k)
    else:
        heapq.heappushpop(best, reading)   # O(log k), O(1) if it cannot get in

assert sorted(best, reverse=True) == [60, 51, 40]  # O(k) memory throughout
```

### タスクの優先度付きキュー

```python
import heapq
import itertools

counter = itertools.count()
queue = []

def submit(priority, task):
    heapq.heappush(queue, (priority, next(counter), task))  # O(log n)

def take():
    priority, _, task = heapq.heappop(queue)  # O(log n)
    return task

submit(2, 'write report')
submit(1, 'fix outage')
submit(2, 'answer email')

assert [take() for _ in range(3)] == ['fix outage', 'write report', 'answer email']
```

## ベストプラクティス

✅ **推奨**:

- 先頭を覗くには `heap[0]` を読む。O(1) で、取り出しと追加は不要
- 追加と取り出しを一緒に行うなら `heappushpop` か `heapreplace` を使う。呼び出しは 1 回で
  リサイズもなく、`heappushpop` は入れない要素を 1 回の比較で返す
- 大きな入力やストリームから少数の要素を取るには `nlargest` か `nsmallest` を使う。メモリは k に
  比例する
- 優先度とペイロードの間にカウンタを置き、同順位のときにペイロードが比較されないようにする
- ソート済みの入力には `merge` を使う。遅延評価で、入力ごとに 1 要素しか保持しない

❌ **避けるべきこと**:

- 少数の要素を取るためにリスト全体をソートすること - 時間 O(m log m)、メモリ O(m)
- 1 つの要素を探すためにヒープを取り出し尽くすこと。ヒープが順序づけるのは根だけ
- 追加のたびに `heapify` を呼ぶこと - O(log n) で済むところが毎回 O(n)
- ソートされていない入力を `merge` に渡すこと。出力はソートされず、何も知らせてくれない

## バージョン別の注記

- **Python 3.14+**: `heapify_max`、`heappush_max`、`heappop_max`、`heappushpop_max`、
  `heapreplace_max` が追加された

## 関連モジュール

- **[queue](queue.md)** - `PriorityQueue` はロック付きの `heapq` ヒープで、生産者スレッドと消費者スレッド向け
- **[sched](sched.md)** - 時刻付きイベントのヒープの上に構築されたイベントスケジューラ
- **[bisect](bisect.md)** - 代わりにリストを完全にソートされた状態に保ち、挿入は O(n)
- **[sorted()](../builtins/sorted.md)** - 上位 k 個だけでなくすべての要素が必要なときは O(m log m)
