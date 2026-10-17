---
source_sha: a15a59a2e896d04888dafc57e64dd677615bec4310ef7fc6de1e8eb9c35a355e
translated: machine
---

# 辞書操作の計算量

`dict` 型はキーと値のペアを挿入順に保持する可変のマッピングです。CPython ではハッシュテーブルなので、
検索・挿入・削除は辞書の大きさに依存せず、すべての要素に触れる操作（コピー、反復、比較）は線形です。

`n` は辞書の要素数、`m` はもう一方のオペランドの要素数です。`update()` や `fromkeys()` に渡す
マッピングまたはイテラブル、あるいは `|` やビューの集合演算の右辺を指します。キーのハッシュ計算と比較は
O(1) とみなし、2 つの値の比較も同様です。O(1) の検索は平均計算量です。すべてのキーが同じハッシュ値を
持つ場合、それぞれ O(n) になります。

## 計算量リファレンス

### dict

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(d)` | O(1) | O(1) | 要素数は保存されている |
| `d[key]`, `d.get(key, default=None)` | 平均 O(1)、最悪 O(n) | O(1) | `d[key]` はキーがなければ `KeyError` を送出する |
| `key in d` | 平均 O(1)、最悪 O(n) | O(1) | |
| `d[key] = value` | 償却 O(1) | O(1) | テーブルを拡張する呼び出しは O(n) で作り直す |
| `del d[key]`, `d.pop(key[, default])` | 平均 O(1)、最悪 O(n) | O(1) | `pop()` に既定値を渡さない限り、キーがなければ `KeyError` を送出する。テーブルは縮小しない |
| `d.setdefault(key, default=None)` | 償却 O(1) | O(1) | 1 回の検索と、キーがないときの挿入 |
| `d.popitem()` | 償却 O(1) | O(1) | 最後に挿入したペアを取り除く。辞書が空なら `KeyError` を送出する |
| `d.clear()` | O(n) | O(1) | すべてのキーと値を解放する |
| `d.copy()` | O(n) | O(n) | 浅いコピー。キーと値は共有され、複製されない |
| `dict.fromkeys(iterable, value=None)` | O(m) | O(m) | すべてのキーが同じ `value` オブジェクトを指す |
| `d.update(other)`, `d \|= other` | 償却 O(m) | O(m) | その場で更新。加えて `other`（マッピングまたはペアのイテラブル）を反復するコスト |
| `d \| other` | O(n + m) | O(n + m) | 新しい辞書。`d` のコピーを `other` で更新したもの。`dict` が扱うのは `dict` か `frozendict` の `other` だけで、それ以外は `other.__ror__` に任される |
| `d` の反復、`reversed(d)` | O(n) | O(1) | 挿入順、またはその逆順 |
| `d == other`, `d != other` | O(n) | O(1) | 順序は無視される。長さが異なれば O(1) |

### ビュー

`d.keys()`、`d.values()`、`d.items()` はビューです。`d` への参照を持ち、何もコピーせずに `d` への
その後の変更をすべて反映します。

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `d.keys()`, `d.values()`, `d.items()` | O(1) | O(1) | |
| `len(view)`, `view.mapping` | O(1) | O(1) | `mapping` は `d` の読み取り専用プロキシ |
| ビューの反復、`reversed(view)` | O(n) | O(1) | |
| `key in d.keys()`, `(key, value) in d.items()` | 平均 O(1)、最悪 O(n) | O(1) | キーの検索 1 回。`items()` ではさらに値の比較 1 回 |
| `value in d.values()` | O(n) | O(1) | 値には索引がないので走査する |
| `view & other` | O(m) | O(min(n, m)) | `keys()` と `items()` のビュー。`other` が集合か `keys()` または `items()` のビューなら時間は O(min(n, m)) |
| `view \| other`, `view - other`, `view ^ other` | O(n + m) | O(n + m) | いずれも新しい `set` を作る |
| `view.isdisjoint(other)` | O(m) | O(1) | `other` が集合か `keys()` または `items()` のビューなら O(min(n, m))。最初の共通要素で止まる |

要素を削除してもテーブルは縮小しません。要素の大半を取り除いた後も、テーブルを走査する操作
（`d` やビューの反復、`copy()`、`d | other`、`other.update(d)`、`d == other`、`dict(d)`）は、
後の挿入でリサイズが起きるまで、辞書の以前の大きさに比例する時間がかかります。`len()` と検索には
影響しません。

## 検索と衝突

検索はキーのハッシュを計算し、ハッシュ値が同じ格納済みのキーとだけ比較します。ハッシュがよく分散して
いれば比較は多くても 1 回です。多くのキーが同じハッシュ値を持つと、検索はそれらと順に比較するので O(n) に
劣化します。

```python
class Key:
    comparisons = 0

    def __init__(self, name, hash_value):
        self.name = name
        self.hash_value = hash_value

    def __hash__(self):
        return self.hash_value

    def __eq__(self, other):
        Key.comparisons += 1
        return self.name == other.name

spread = {Key(i, i): i for i in range(100)}     # O(n)
Key.comparisons = 0
assert spread[Key(99, 99)] == 99                # O(1)
assert Key.comparisons == 1                     # only the key with the same hash

colliding = {Key(i, 1): i for i in range(100)}  # O(n²) - each insertion compares
Key.comparisons = 0
assert colliding[Key(99, 1)] == 99              # O(n) - compares every key before it
assert Key.comparisons == 100
```

## 削除してもテーブルは縮小しない

`del` と `pop()` はテーブルを最大の大きさのまま残すので、走査はそれまでに持っていたすべてのスロットを
たどります。要素の大半を失った辞書を `copy()` するとコンパクトな辞書ができ、その後の走査は再び安く
なります。

```python
import sys

d = {i: i for i in range(100_000)}
full = sys.getsizeof(d)
for i in range(10, 100_000):
    del d[i]                       # O(1) each

assert len(d) == 10                # O(1)
assert sys.getsizeof(d) == full    # still sized for 100,000 items
keys = list(d)                     # O(100,000): walks the old table

d = d.copy()                       # O(100,000) once
assert sys.getsizeof(d) < full     # sized for 10 items
assert list(d) == keys             # O(10)
```

### 最も古い要素の削除

テーブルの先頭でも同じことが起きます。`next(iter(d))` はそれまでの削除で空いたスロットをすべて
読み飛ばすので、最も古いキーをループで削除すると 1 回あたり O(n)、辞書全体で O(n²) かかります。
`collections.OrderedDict.popitem(last=False)` は最も古い要素を O(1) で取り除きます。

```python
from collections import OrderedDict

d = dict.fromkeys(range(5))
oldest = next(iter(d))      # O(1) here; O(deleted so far) in a loop
del d[oldest]
assert list(d) == [1, 2, 3, 4]

od = OrderedDict.fromkeys(range(5))
assert od.popitem(last=False) == (0, None)   # O(1)
assert list(od) == [1, 2, 3, 4]
```

## ビュー

ビューは O(1) で作られ、使った時点の辞書を反映します。`keys()` と `items()` での所属判定は
ハッシュ検索、`values()` での所属判定は走査です。`keys()` と `items()` の集合演算は新しい `set`
を返します。

```python
d = {'a': 1, 'b': 2}
keys = d.keys()                 # O(1) - no copy
d['c'] = 3
assert list(keys) == ['a', 'b', 'c']  # O(n) - sees the new key

assert 'b' in keys              # O(1)
assert ('b', 2) in d.items()    # O(1) - key lookup, then one value comparison
assert 3 in d.values()          # O(n) - a scan

assert keys & {'a', 'z'} == {'a'}           # O(min(n, m)) with a set
assert keys - ['a'] == {'b', 'c'}           # O(n + m)
assert keys.isdisjoint({'x', 'y'})          # O(min(n, m)) with a set
assert keys.mapping['a'] == 1               # O(1) - a read-only proxy
```

## | と update() による結合

`d | other` は `d` をコピーしてから `other` の要素をすべて挿入するので、どちらが大きくても
O(n + m) です。`d |= other` と `d.update(other)` は `d` 自体に挿入し、O(m) で済みます。
`update()` はペアのイテラブルとキーワード引数も受け付けます。

```python
defaults = {'color': 'red', 'size': 10}
overrides = {'size': 12}

merged = defaults | overrides       # O(n + m) - a new dict
assert merged == {'color': 'red', 'size': 12}
assert defaults['size'] == 10

config = defaults
config |= overrides                 # O(m) - in place
assert config is defaults and defaults['size'] == 12

config.update([('debug', True)], verbose=False)  # O(m)
assert list(config) == ['color', 'size', 'debug', 'verbose']
```

## 挿入順序

反復は挿入順に従い、`reversed()` はそれを逆にたどります。既存のキーへの代入はその位置を保ちます。
`popitem()` は最後に挿入したペアを取り除きます。

```python
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
d['a'] = 10                         # O(1) - keeps its position

assert list(d) == ['a', 'b', 'c']   # O(n)
assert list(reversed(d)) == ['c', 'b', 'a']  # O(n)
assert d.popitem() == ('c', 3)      # O(1) - last in, first out
assert d == {'b': 2, 'a': 10}       # O(n) - order is ignored
```

## キーはハッシュ可能でなければならない

検索のたびに、また `d[key] = value` のたびにキーはハッシュされます。リスト、辞書、集合は可変で
ハッシュ不可能なのでキーにできません。同じハッシュ可能な要素からなるタプルや `frozenset` ならキーに
できます。

```python
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key',
}
assert d[frozenset([2, 1])] == 'frozen_key'   # O(1) after hashing the key

for key in ([1, 2], {1, 2}, {'a': 1}):
    try:
        d[key] = 'fails'
    except TypeError as error:
        assert 'unhashable' in str(error)
    else:
        raise AssertionError(f'{type(key).__name__} must not be usable as a key')
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- キーによる検索には辞書を使う。リストで必要な O(n) の走査ではなく O(1) で済む
- キーがない場合の処理には `get()` か `setdefault()` を使い、検索を 2 回ではなく 1 回にする
- 辞書への追加には `d |= other` か `update()` を使えば O(m)。`d | other` は先に `d` をコピーする
- 要素の大半を失った辞書はコピーし、その後の走査を現在の大きさのコストにする

❌ **避けるべきこと**:

- ループ内での `value in d.values()` - 各判定が O(n)。逆引きの辞書か値の集合を持っておく
- `del d[next(iter(d))]` をループで使って最も古いキーを削除すること - 全体で O(n²)。
  `OrderedDict.popitem(last=False)` を使う
- `d = d | other` を繰り返して辞書を組み立てること - 毎回それまでの内容をすべてコピーする
- `__hash__` の質が悪いキー - 多くが衝突すると、すべての検索が O(n) に劣化する

## バージョン別の注記

- **Python 3.7+**: 挿入順序が言語仕様になった。CPython 3.6 ではすでに保たれていた
- **Python 3.9+**: 結合演算子 `|` と更新演算子 `|=`
- **Python 3.15+**: [`frozendict`](frozendict.md)、不変でハッシュ可能な辞書

## 関連する型

- **[集合](set.md)** - 順序を持たない重複のない要素
- **[frozendict](frozendict.md)** - 不変でハッシュ可能な辞書（Python 3.15+）
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - 既定値を自動で用意する
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - 両端からの O(1) の削除と `move_to_end()`
- **[ChainMap](../stdlib/collections.md#chainmap)** - 複数の辞書をまとめて見る

## さらに読む

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython の辞書実装を掘り下げた解説
