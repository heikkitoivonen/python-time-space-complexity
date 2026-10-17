---
source_sha: bc1c0d5a1529618fadecea5515f24b98a32b01bad53b2296163318b2ea145d27
translated: machine
---

# 集合操作の計算量

`set` 型は、一意でハッシュ可能な要素からなる、変更可能で順序を持たないコレクションです。値を持たない
`dict` のようなハッシュテーブルなので、メンバーシップ判定・追加・削除は平均 O(1) で、集合演算には
検索すべき要素の数だけコストがかかります。

`n` は集合の要素数、`m` はもう一方のオペランドの要素数、またはイテラブルなオペランドが生成する要素数です。
各行はオペランド 1 つ分の計算量です。複数のオペランドを受け取るメソッドはそれらを順に適用し、コストは
その合計になります。要素のハッシュ計算と比較は O(1) とみなします。

## 計算量リファレンス

### set

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | 要素数は保存されている |
| `x in s` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ検索。最悪ケースはハッシュ衝突時。集合の `x` は frozenset としてハッシュされ、k 個の要素に対して O(k)、3.14 より前は空間も O(k) |
| `set` の反復 | O(n) | O(1) | 順序は任意 |
| `s.add(x)` | 償却 O(1) | 償却 O(1) | ときどきリサイズでテーブルを O(n) で作り直す |
| `s.remove(x)`, `s.discard(x)` | 平均 O(1)、最悪 O(n) | O(1) | `x` がないとき `remove()` は `KeyError` を送出する。集合の `x` は `x in s` と同様にハッシュされる |
| `s.pop()` | 空になるまで取り出す場合は償却 O(1) | O(1) | 任意の要素を、前回の `pop()` が止まった位置から探して取り除く。空なら `KeyError` を送出する。他の方法で削除した後は、1 回の呼び出しでテーブルの以前のサイズ分のコストがかかることがある |
| `s.clear()` | O(n) | O(1) | すべての要素を解放する |
| `s.copy()` | O(n) | O(n) | 浅いコピー。コピーは保持する要素数に合ったサイズになる |
| `s == other`, `s != other` | O(n) | O(1) | 長さが異なれば O(1) |
| `s <= other`, `s < other` | O(n) | O(1) | 集合に対する `issubset()` と同じ |
| `s >= other`, `s > other` | O(m) | O(1) | 集合に対する `issuperset()` と同じ |

### 集合演算

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `s.union(other)`, `s \| other` | O(n+m) | O(n+m) | 新しい集合を返す |
| `s.intersection(other)`, `s & other` | O(min(n,m))。`other` が集合でなければ O(m) | O(min(n,m)) | 小さいほうの集合の要素を大きいほうで検索する |
| `s.difference(other)`, `s - other` | O(n)。`other` が集合でなければ O(n+m) | O(n) | 新しい集合を返す |
| `s.symmetric_difference(other)`, `s ^ other` | O(n+m) | O(n+m) | 新しい集合を返す |
| `s.issubset(other)` | O(n)。`other` が集合でなければ O(n+m) | O(1)。`other` が集合でなければ O(m) | `other` がより短い集合なら O(1) |
| `s.issuperset(other)` | O(m) | O(1) | `s` にない `other` の要素が最初に見つかった時点で止まる |
| `s.isdisjoint(other)` | O(min(n,m))。`other` が集合でなければ O(m) | O(1) | 最初の共通要素で止まる。集合のサブクラスは一般のイテラブルと同様に反復される |

### インプレース更新

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `s.update(other)`, `s \|= other` | 償却 O(m) | 償却 O(m) | `s` は最大 m 要素増える |
| `s.intersection_update(other)`, `s &= other` | 償却 O(min(n,m))。`other` が集合でなければ償却 O(m) | O(min(n,m)) | 積集合を作って置き換える。古いテーブルの解放は O(n) だが、そのテーブルを埋めた挿入がその分を支払っている |
| `s.difference_update(other)`, `s -= other` | 償却 O(min(n,m))。`other` が集合でなければ償却 O(m) | O(n) | `s` からその場で取り除く |
| `s.symmetric_difference_update(other)`, `s ^= other` | 償却 O(m) | 償却 O(m) | `s` は最大 m 要素増える。集合でない `other` はまず集合にコピーされる |

演算子は集合と frozenset しか受け付けませんが、メソッドは任意のイテラブルも受け付けます。すべての要素が
同じハッシュ値になる最悪の場合、O(1) の操作は O(n) かかり、一方の集合の全要素をもう一方で検索する操作も
それに応じて遅くなります。

`remove()`、`discard()`、`pop()` で要素を削除してもテーブルは縮小しません。大半の要素を削除した後も、
テーブルを走査する操作 (反復、`copy()`、`clear()`、`|`、`-`、`^`、`&=`、比較、`set(s)`) は、後の挿入で
リサイズが起きるまで集合の以前のサイズに比例した時間がかかり、1 回の `pop()` も同様になり得ます。
`len()` とメンバーシップ判定は影響を受けません。`&=` とそのメソッドは常にコンパクトなテーブルを残します。

## 集合演算

演算子は集合と frozenset しか受け付けないため、右辺がリストだと `TypeError` になります。メソッドは任意の
イテラブルを受け取り、順に要素へ変換します。

```python
a = {1, 2, 3}
b = {2, 3, 4}

assert a | b == {1, 2, 3, 4}     # O(n+m)
assert a & b == {2, 3}           # O(min(n,m))
assert a - b == {1}              # O(n)
assert a ^ b == {1, 4}           # O(n+m)

assert a.union([3, 4]) == {1, 2, 3, 4}  # O(n+m): a method takes any iterable
try:
    a | [3, 4]
except TypeError as error:
    assert 'unsupported operand' in str(error)
else:
    raise AssertionError('an operator takes only sets')

a |= b                           # O(m): grows a in place
assert a == {1, 2, 3, 4}
```

## メンバーシップの判定

リストは `x` を要素と 1 つずつ比較しますが、集合は `x` を一度ハッシュして平均でいくつかのスロットを
調べるだけです。リストから集合への変換は一度だけ O(n) かかるので、多くの値を検索するなら元が取れます。

```python
numbers = list(range(1_000))
lookup = set(numbers)          # O(n) once

assert 999 in numbers          # O(n): scans the whole list
assert 999 in lookup           # O(1) avg
assert -1 not in lookup        # O(1) avg, found or not

# A set can be looked up in a set of frozensets, hashed as a frozenset
groups = {frozenset({1, 2}), frozenset({3})}
assert {1, 2} in groups        # O(k) to hash the k-element key
```

## 削除してもテーブルは縮小しない

削除してもテーブルは最大時のサイズのままなので、走査には満杯だったときと同じコストがかかります。
`copy()` はコンパクトなテーブルを返します。

```python
import sys

s = set(range(100_000))
full = sys.getsizeof(s)
for i in range(10, 100_000):
    s.discard(i)                   # O(1) each

assert len(s) == 10                # O(1)
assert sys.getsizeof(s) == full    # still sized for 100,000 elements
items = list(s)                    # O(100,000): walks the old table

s = s.copy()                       # O(100,000) once
assert sys.getsizeof(s) < full     # sized for 10 elements
assert sorted(s) == sorted(items)  # O(10)
```

`pop()` だけで集合を空にする場合、各呼び出しが前回止まった位置から始まるので、各スロットを一度ずつ
たどるだけです。他の方法で削除した後の `pop()` は、まず前方の空きスロットを読み飛ばす必要があります。

```python
s = set(range(1_000))
drained = 0
while s:
    s.pop()                        # O(1) amortized: the n calls walk the table once
    drained += 1
assert drained == 1_000

try:
    s.pop()
except KeyError as error:
    assert 'pop from an empty set' in str(error)
else:
    raise AssertionError('pop() on an empty set raises')
```

## よくあるパターン

### 重複の除去

```python
items = [3, 1, 3, 2, 1]

# Bad: O(n²) - each `in` scans the list built so far
unique = []
for item in items:
    if item not in unique:
        unique.append(item)
assert unique == [3, 1, 2]

# Good: O(n), but the order is arbitrary
unique = set(items)
assert unique == {1, 2, 3}

# Best when order matters: O(n), keeping the first occurrence of each
assert list(dict.fromkeys(items)) == [3, 1, 2]
```

### 高速な絞り込み

```python
values = list(range(10_000))
excluded = [3, 30, 300, 3_000]

# Bad: O(n·m) - scans the excluded list for every value
slow = [x for x in values if x not in excluded]

# Good: O(n + m) - one O(m) conversion, then O(1) per value
excluded_set = set(excluded)
fast = [x for x in values if x not in excluded_set]

assert slow == fast and len(fast) == 10_000 - 4
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- 繰り返しのメンバーシップ判定には集合を使う: 1 回 O(1)、リストなら O(n)
- 積集合はどちらの順序で取ってもよい: 集合オペランドでの `&` と `intersection()` は小さいほうだけを走査する
- 元の順序のまま一意な要素が必要なら `dict.fromkeys()` を使う
- 大半の要素を失った集合を何度も走査する前にコピーし、走査コストを保持している要素数に見合うものにする

❌ **避けるべきこと**:

- 別のコレクションを回すループ内での `x in some_list`: O(n·m)、集合なら O(n + m)
- 反復順序への依存: 順序は挿入順ではなくハッシュテーブルに従う
- 他の方法で大半の要素を削除した後も `pop()` が O(1) だと期待すること

## バージョン別の注記

- **Python 3.14+**: 集合を要素として検索する場合 (`{1, 2} in s`、`s.discard({1, 2})`)、その場で
  ハッシュするので空間は O(1)。それ以前のバージョンは一時的な frozenset にコピーするため空間は O(k)

## 関連する型

- **[Frozenset](frozenset.md)** - 検索コストが同じ、変更不可能でハッシュ可能な集合
- **[set()](set_func.md)** - イテラブルからの集合の構築
- **[Dict](dict.md)** - 値を持つ同じハッシュテーブル。`dict.fromkeys()` は挿入順を保つ

## さらに読む

- [CPython Internals: set](https://zpoint.github.io/CPython-Internals/BasicObject/set/set.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython の集合実装を掘り下げた解説
