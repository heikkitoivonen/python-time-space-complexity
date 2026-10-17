---
source_sha: 0f682082c1e815cf6cb74518bbbdc670c90d687d42c87d1afd5e6f989b5ac7c8
translated: machine
---

# タプル操作の計算量

`tuple` 型は不変で順序を持つシーケンスです。CPython はこれを参照の固定長配列として格納するため、添字アクセスは直接行われ、要素の挿入、削除、リサイズが必要になることはありません。タプルは変更できないので、厳密に `tuple` 型であるタプルをコピーすると、そのタプル自身が返されます。

`n` はタプルの長さ、`k` は数値引数の値（添字または繰り返し回数）、`i:j` はスライスの範囲、`len(t1)`、`len(t2)` はオペランドの長さです。ステップを持つスライスは `m` 個の要素を選びます。添字は負の値を正規化した後のものとして数えます。要素 1 つの比較またはハッシュ計算は O(1) とみなします。

## 計算量リファレンス

### tuple

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(t)` | O(1) | O(1) | 長さはタプルに格納されており、数え直さない |
| `t[k]` | O(1) | O(1) | 直接の添字アクセス |
| `t[i:j]`（スライス） | O(j-i) | O(j-i) | ステップ付きでは O(m)。厳密に `tuple` 型であるタプルの `t[:]` は `t` 自身を返す |
| `t.index(x)` | O(n) | O(1) | 線形探索。`t.index(x, i, j)` は `t[i:j]` だけを探索し O(j-i) |
| `t.count(x)` | O(n) | O(1) | 線形走査 |
| `x in t`（所属判定） | O(n) | O(1) | 線形探索 |
| `tuple(t)`、`copy.copy(t)` | O(1) | O(1) | `t` が厳密に `tuple` 型なら `t` 自身を返す。タプルには `copy()` メソッドがない |
| `tuple(iterable)` | O(n) | O(n) | n = イテラブルが生成する要素数。[tuple()](tuple_func.md) を参照 |
| `t1 + t2`（連結） | O(len(t1)+len(t2)) | O(len(t1)+len(t2)) | |
| `t * k`（繰り返し） | O(nk) | O(nk) | k ≤ 0 なら空のタプル |
| `t1 == t2` | O(min(len(t1), len(t2))) | O(1) | 長さが異なっても要素を比較する。最初の等しくない組で止まる |
| `t1 < t2`、`<=`、`>`、`>=` | O(min(len(t1), len(t2))) | O(1) | 最初の等しくない組で止まる |
| `for x in t`（反復） | O(n) | O(1) | 1 ステップあたり O(1) |
| `reversed(t)` | O(1) | O(1) | 遅延イテレータ。たどると O(n) |
| `min(t)`、`max(t)` | O(n) | O(1) | n-1 回の比較 |
| `hash(t)` | 初回は O(n)、3.14 以降は 2 回目から O(1) | O(1) | 3.11-3.13 では毎回計算し直す。ハッシュ不可能な要素があれば `TypeError` を送出し、何もキャッシュされない |

## コピーは同じタプルを返す

厳密に `tuple` 型であるタプルのコピーは元のタプルと決して違いが生じないため、`tuple(t)`、`copy.copy(t)`、`t[:]` は O(1) で `t` 自身を返します。サブクラスのインスタンスは O(n) でコピーされます。

```python
import copy

t = tuple(range(1_000))
assert tuple(t) is t  # O(1)
assert copy.copy(t) is t  # O(1)
assert t[:] is t  # O(1)


class Pair(tuple):
    pass


p = Pair((1, 2))
assert tuple(p) is not p and type(tuple(p)) is tuple  # O(n): a subclass is copied
```

## ハッシュ

`hash(t)` はすべての要素のハッシュ値を組み合わせるため、初回の呼び出しは O(n) です。3.14 以降は結果がタプルに保持され、以後の呼び出しは O(1) です。3.11-3.13 では呼び出すたびに要素をたどり直します。キャッシュはオブジェクトごとのもので、別に作られた等しいタプルは自分自身の初回ハッシュのコストを払います。

```python
import sys

calls = 0


class Key:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Key) and self.value == other.value

    def __hash__(self):
        global calls
        calls += 1
        return hash(self.value)


t = tuple(Key(i) for i in range(100))
hash(t)  # O(n): hashes every element
assert calls == 100

calls = 0
hash(t)  # O(1) on 3.14+, O(n) before
assert calls == (0 if sys.version_info >= (3, 14) else 100)

try:
    hash((1, []))
except TypeError as exc:
    assert "unhashable type: 'list'" in str(exc)
else:
    raise AssertionError("expected TypeError")
```

## タプルの比較

`==` は最初に長さを確認しません。共通の先頭部分をたどり、最初の等しくない組で止まり、すべての組が等しいまま短い方のタプルが尽きたときに初めて長さを見ます。[リスト](list.md)と違い、長さの異なるタプルでも共通の先頭部分を比較します。

```python
compared = 0


class Item:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        global compared
        compared += 1
        return self.value == other.value

    __hash__ = None


short = tuple(Item(i) for i in range(999))
long = tuple(Item(i) for i in range(1_000))
assert short != long  # O(min(len(t1), len(t2))): the common prefix is compared
assert compared == 999

compared = 0
assert list(short) != list(long)  # a list answers from the lengths alone
assert compared == 0
```

## タプルの組み立て

`t += (x,)` は新しいタプルを作るため、ループ内ではそれまでに集めたものをステップごとにすべてコピーし、全体で O(n²) になります。リストに集めてから一度だけ変換してください。

```python
slow = ()
for i in range(1_000):
    slow += (i,)  # O(len(slow)): copies the tuple each time

items = []
for i in range(1_000):
    items.append(i)  # O(1) amortized
fast = tuple(items)  # O(n), once

assert slow == fast == tuple(range(1_000))
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- 気兼ねなくコピーする: 厳密に `tuple` 型であるタプルの `tuple(t)` と `t[:]` は O(1)
- 要素がハッシュ可能なら、タプルを辞書のキーや集合の要素に使う。3.14 以降、そのハッシュ値はタプルごとに一度だけ計算される
- 要素をリストに集め、`tuple()` を一度だけ呼ぶ: 全体で O(n)

❌ **避けるべきこと**:

- ループ内の `t += (x,)`: ステップごとにタプルをコピーし、全体で O(n²)
- 別のループの中での `x in t`: 判定ごとに O(n)。[集合](set.md)を一度作れば平均 O(1) で検索できる

## バージョン別の注記

- **Python 3.14+**: `hash(t)` は結果をタプルに保持するため、2 回目以降の呼び出しは O(1)

## 関連する型

- **[リスト](list.md)** - 可変の代替
- **[tuple()](tuple_func.md)** - イテラブルからのタプルの作成
- **[namedtuple](../stdlib/namedtuple.md)** - 名前付きフィールドを持つタプル
- **[データクラス](../stdlib/dataclasses.md)** - 名前付きフィールドを持つ可変のレコード

## さらに読む

- [CPython Internals: tuple](https://zpoint.github.io/CPython-Internals/BasicObject/tuple/tuple.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython のタプル実装を掘り下げた解説
