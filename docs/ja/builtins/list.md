---
source_sha: e5d540424cf900e9f6a380860ebd4036e31f6ee63640234552e2d102a7e0b262
translated: machine
---

# リスト操作の計算量

`list` 型は可変で順序を持つシーケンスです。CPython では参照の動的配列として実装されています。各要素への参照を保持し、末尾での拡張でリサイズがめったに必要にならないよう、多めに領域を確保します。

`n` はリストの長さ、`k` は数値引数の値（添字または繰り返し回数）、`i:j` はスライスの範囲、`len(t)` はもう一方のオペランドの長さです。ステップ `s` を持つスライスは `m` 個の要素を選び、その `i` は選ばれる最小の添字です。添字は負の値を正規化した後のものとして数えます。要素 2 つの比較と `key` 関数の呼び出しは O(1) とみなします。すでにリストやタプルではないオペランドを反復する場合は、そのコストが加わります。「償却」とは、個々の呼び出しがときおり O(n) のリサイズを払うものの、そのコストがそれ以前の呼び出しに分散されることを意味します。

## 計算量リファレンス

### list

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(l)` | O(1) | O(1) | 長さはリストに格納されており、数え直さない |
| `l[k]` | O(1) | O(1) | 添字による直接アクセス |
| `l[k] = x` | O(1) | O(1) | 1 つのスロットを置き換える |
| `del l[k]` | O(n-k) | O(1) | k より後ろの要素を 1 つ左へずらす |
| `l.append(x)` | 償却 O(1) | 償却 O(1) | |
| `l.insert(0, x)` | O(n) | 償却 O(1) | すべての要素が 1 つ右へ移動する |
| `l.insert(k, x)` | 償却 O(n-k) | 償却 O(1) | 添字 k 以降の要素を 1 つ右へずらす |
| `l.remove(x)` | O(n) | O(1) | 先頭から探索し、一致した要素より後ろをずらす |
| `l.pop()` | 償却 O(1) | O(1) | 末尾の要素を取り除く。何もずらさない |
| `l.pop(0)` | O(n) | O(1) | 残りのすべての要素が 1 つ左へ移動する |
| `l.pop(k)` | 償却 O(n-k) | O(1) | k より後ろの要素を 1 つ左へずらす |
| `l.clear()` | O(n) | O(1) | すべての要素を解放する |
| `l.index(x)` | O(n) | O(1) | 線形探索。`l.index(x, i, j)` は `l[i:j]` だけを探索し、O(j-i) |
| `l.count(x)` | O(n) | O(1) | 線形走査 |
| `l.sort(key=None, reverse=False)` | O(n log n) | O(n) | 整列済みまたは逆順に整列済みの入力では比較は O(n) 回だけ。`key` は要素ごとに 1 回呼ばれる |
| `l.reverse()` | O(n) | O(1) | その場で反転する |
| `l.copy()` | O(n) | O(n) | 浅いコピー |
| `l.extend(t)` | 償却 O(len(t)) | O(len(t)) | これに t の反復コストが加わる |
| `l += t` | 償却 O(len(t)) | O(len(t)) | `l.extend(t)` と同じ。リストは同じオブジェクトのまま |
| `l[i:j]`（スライス） | O(j-i) | O(j-i) | ステップ付きでは O(m) |
| `l[i:j] = t` | len(t) == j-i なら O(j-i)、それ以外は償却 O(n-i+len(t)) | O(j-i+len(t)) | 長さが等しければその場で上書きする。そうでなければ j 以降がすべて移動する |
| `l[i:j:s] = t`（s ≠ 1） | O(m) | O(m) | t はちょうど m 個の要素を持たなければならないので、何も移動しない |
| `del l[i:j]` | O(n-i) | O(j-i) | j 以降がすべて左へ移動する |
| `del l[i:j:s]` | O(n-i) | O(m) | i 以降がすべて詰められる |
| `l1 + l2`（連結） | O(len(l1)+len(l2)) | O(len(l1)+len(l2)) | 新しいリスト |
| `l * k`（繰り返し） | O(nk) | O(nk) | n·k 個の参照を持つ新しいリスト。k ≤ 0 なら空のリスト |
| `l *= k` | O(nk) | O(nk) | その場で行う。k ≤ 0 ならリストを O(n) で空にする |
| `l1 == l2` | O(n) | O(1) | 長さが異なれば O(1)。そうでなければ最初の等しくない組で止まる |
| `l1 < l2`, `<=`, `>`, `>=` | O(min(len(l1), len(l2))) | O(1) | 最初の等しくない組で止まる |
| `for x in l`（反復） | O(n) | O(1) | 1 ステップあたり O(1) |
| `reversed(l)` | O(1) | O(1) | 遅延イテレータ。走査すると O(n) |
| `x in l`（メンバーシップ） | O(n) | O(1) | 線形探索 |
| `min(l)`, `max(l)` | O(n) | O(1) | 比較は n-1 回 |

## 末尾での拡張

`append()` が償却 O(1) なのは、リサイズが後続の追加のための領域を確保するので、ほとんどの追加はリストがすでに持っている領域に書き込むだけで済むからです。

```python
import sys

lst = []
resizes = 0
size = sys.getsizeof(lst)
for i in range(10_000):
    lst.append(i)  # O(1) amortized
    if sys.getsizeof(lst) != size:
        resizes += 1
        size = sys.getsizeof(lst)

assert len(lst) == 10_000
assert resizes < 100
```

## 先頭での操作

添字 0 での挿入や削除は他のすべての要素を移動させるので、1 回ごとに O(n)、それを繰り返すループは O(n²) になります。`collections.deque` は両端での追加と削除が O(1) です。

```python
from collections import deque

lst = list(range(10_000))
lst.insert(0, -1)  # O(n): every element moves one slot right
assert lst[0] == -1 and len(lst) == 10_001
assert lst.pop(0) == -1  # O(n): every element moves back

queue = deque(range(10_000))
queue.appendleft(-1)  # O(1)
assert queue.popleft() == -1  # O(1)
```

## スライスへの代入

スライスを同じ個数の要素で置き換えると、その場で上書きされます。それ以外の長さでは隙間が開くか閉じるので、スライスより後ろがすべて移動します。拡張スライス（ステップが 1 以外）は、選ぶ要素とちょうど同じ個数しか受け付けません。

```python
lst = list(range(10))
lst[2:5] = ["a", "b", "c"]  # O(j-i): same length, overwritten in place
assert lst == [0, 1, "a", "b", "c", 5, 6, 7, 8, 9]

lst[2:5] = ["x"]  # O(n-i+len(t)): the tail moves left to close the gap
assert lst == [0, 1, "x", 5, 6, 7, 8, 9]

lst[::2] = "ABCD"  # O(m)
assert lst == ["A", 1, "B", 5, "C", 7, "D", 9]

try:
    lst[::2] = "AB"
except ValueError as exc:
    assert "sequence of size 2 to extended slice of size 4" in str(exc)
else:
    raise AssertionError("expected ValueError")
```

## リストの組み立て

`l + t` は新しいリストを作るので、ループ内の `l = l + t` は毎回それまでに作ったものすべてをコピーします。`l += t` と `extend()` は既存のリストに償却 O(len(t)) で追加します。

```python
parts = [[i] for i in range(1_000)]

slow = []
for part in parts:
    slow = slow + part  # O(len(slow)): copies the list each time

fast = []
for part in parts:
    fast += part  # O(len(part)) amortized

assert slow == fast == list(range(1_000))
```

## ソート

`sort()` は安定で適応的です。すでに整列済み、または逆順に整列済みの入力では比較は O(n) 回だけです。`key` 関数は比較ごとではなく、要素ごとに 1 回呼ばれます。

```python
calls = 0


def key(word):
    global calls
    calls += 1
    return word.lower()


words = ["pear", "Apple", "fig", "banana"]
words.sort(key=key)  # O(n log n)
assert words == ["Apple", "banana", "fig", "pear"]
assert calls == len(words)
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- 末尾への追加は `append()` か `extend()` で行う。要素あたり償却 O(1)
- 逆順にリストを組み立てるときは末尾に追加してから `reverse()` を 1 回呼ぶ。全体で O(n)
- `len(t) == j - i` となる `l[i:j] = t` で連続部分を上書きする。後ろは何も移動しない
- `sort()` には `functools.cmp_to_key()` による比較ではなく `key=` を渡す。キー関数は n 回、比較関数は比較ごとに 1 回呼ばれる

❌ **避けるべきこと**:

- ループ内での `insert(0, x)` や `pop(0)`。どちらも O(n) - `collections.deque` を使う
- ループ内での `l = l + [x]`。毎回リストをコピーするので全体で O(n²)
- 別のループの中での `x in l`。判定ごとに O(n) - [集合](set.md) を一度作れば探索は平均 O(1)

## 関連する型

- **[Deque](../stdlib/collections.md#deque)** - 両端での追加と取り出しが O(1)
- **[配列](../stdlib/array.md)** - 要素数の多い数値リストでは、よりメモリ効率が高い
- **[タプル](tuple.md)** - 不変の代替
- **[list()](list_func.md)** - イテラブルからのリストの作成

## さらに読む

- [CPython Internals: list](https://zpoint.github.io/CPython-Internals/BasicObject/list/list.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython のリスト実装を掘り下げた解説
