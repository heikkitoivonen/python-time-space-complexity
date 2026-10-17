---
source_sha: 0aa31d8e74b3cf287660536daef3aa50acfed3e07167aeb3888371da0ed5c807
translated: machine
---

# len() 関数の計算量

`len(obj)` はコンテナ内の要素の個数を返します。組み込みのコンテナはどれも要素数をオブジェクト内に保持しているので、`len()` は数えずにその値を読み出します。コンテナの大きさには関係ありません。それ以外のオブジェクトに対しては、`len()` はそのクラスが定義する `__len__` メソッドを呼び出し、そのメソッドのコストがかかります。

組み込み型の行はコンテナの大きさに依存しません。`f` はクラスが自分で定義するメソッド（`__len__`、`__bool__`、`__length_hint__`）にかかる時間で、O(1) の呼び出しに上乗せされます。そのメソッドが確保するメモリは O(1) の空間に上乗せされます。`ChainMap` では、`m` はマップの数、`t` はすべてのマップのキーを重複も含めて合計した数、`u` はそのうち互いに異なるキーの数です。

## 計算量リファレンス

### 組み込み型

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(lst)`, `len(tpl)` | O(1) | O(1) | `list` と `tuple` |
| `len(s)` | O(1) | O(1) | `str`: エンコード後のバイトではなく、文字（コードポイント）を数えます |
| `len(b)`, `len(ba)` | O(1) | O(1) | `bytes` と `bytearray`: バイトを数えます |
| `len(mv)` | O(1) | O(1) | 1 次元以上の `memoryview`: 要素の総数ではなく、最初の次元の長さです |
| `len(d)`, `len(d.keys())`, `len(d.values())`, `len(d.items())` | O(1) | O(1) | `dict` とそのビュー |
| `len(fd)` | O(1) | O(1) | `frozendict`、Python 3.15+ |
| `len(st)`, `len(fs)` | O(1) | O(1) | `set` と `frozenset` |
| `len(r)` | O(1) | O(1) | `range`: 長さは range の生成時に一度だけ計算されます。`sys.maxsize` を超えると `OverflowError` を送出します |

### 標準ライブラリのコンテナ

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(dq)` | O(1) | O(1) | `collections.deque` |
| `len(dd)`, `len(od)`, `len(c)` | O(1) | O(1) | `defaultdict`、`OrderedDict`、`Counter` は `dict` のサブクラスです |
| `len(cm)` | O(m + t) | O(m + u) | `collections.ChainMap` は呼び出しのたびに、すべてのマップのすべてのキーから集合を作ります |

### その他のオブジェクト

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(obj)` | O(f) | O(1) | `type(obj).__len__` を呼び出します。インスタンス属性の `__len__` は無視されます。結果は 0 から `sys.maxsize` までの整数（`int`、または `__index__` を持つオブジェクト）でなければなりません |
| `len(gen)`, `len(iterator)` | O(1) | O(1) | ジェネレータと、`__len__` を持たないイテレータには長さがなく、`TypeError` を送出します |
| `bool(obj)`, `if obj:` | O(1) または O(f) | O(1) | 組み込みのコンテナでは O(1)。`__len__` があり `__bool__` がないクラスは、`__len__` が 0 以外を返すとき真になります |
| `operator.length_hint(obj, default=0)` | O(1) または O(f) | O(1) | 長さがあれば `len(obj)`、なければ `obj.__length_hint__()`、それもなければ `default`。`obj` 自体を反復することはありません |

## 組み込みのコンテナ

`len()` のコストは、要素が 3 個のコンテナでも 100 万個のコンテナでも同じです。`str` では文字を数えるので、エンコード後の `bytes` の長さとは異なることがあります。

```python
items = list(range(1_000_000))
assert len(items) == 1_000_000  # O(1)
assert len((1, 2, 3)) == 3  # O(1)

d = {"a": 1, "b": 2}
assert len(d) == len(d.keys()) == len(d.items()) == 2  # O(1)
assert len({1, 2, 2, 3}) == 3  # O(1)

s = "café"
assert len(s) == 4  # O(1) - characters
assert len(s.encode("utf-8")) == 5  # O(1) - bytes, after an O(n) encode

grid = memoryview(bytes(12)).cast("B", shape=[3, 4])
assert len(grid) == 3  # O(1) - the first dimension
assert grid.nbytes == 12
```

## range オブジェクト

range は生成時に `start`、`stop`、`step` から長さを計算し、`len()` は保存された値を返します。range は `sys.maxsize` より長くなれますが、`len()` はインデックスに収まる大きさの整数を返さなければならないため、そのような range には `OverflowError` を送出します。添字アクセスと `in` は引き続き使えます。

```python
import sys

r = range(0, 10**9, 3)
assert len(r) == 333_333_334  # O(1)

huge = range(10**20)
try:
    len(huge)
except OverflowError as error:
    assert "too large" in str(error)
else:
    raise AssertionError("expected OverflowError")

assert 10**20 > sys.maxsize
assert huge[-1] == 10**20 - 1  # O(1)
assert 10**19 in huge  # O(1)
```

## __len__ を持つクラス

`len(obj)` はオブジェクトのクラスの `__len__` を呼び出すので、コストはそのメソッドで決まります。個数を保持しているか組み込みのコンテナに委ねるメソッドは O(1)、反復して数えるメソッドは呼び出しのたびに O(n) です。`len()` は結果を検査します。負の値は `ValueError` を、整数でない値は `TypeError` を送出します。

```python
class Stored:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return len(self.items)  # O(1) - delegates to the list


class Counted:
    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return sum(1 for _ in self.items)  # O(n) - walks every item on each call


assert len(Stored(range(5))) == len(Counted(range(5))) == 5


class Negative:
    def __len__(self):
        return -1


try:
    len(Negative())
except ValueError as error:
    assert ">= 0" in str(error)
else:
    raise AssertionError("expected ValueError")
```

クラスが `__bool__` を定義していない場合、真偽値の判定にも `__len__` が使われます。そのため `if obj:` のコストは `len(obj)` と同じです。

```python
class Box:
    calls = 0

    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        Box.calls += 1
        return len(self.items)


assert not Box([])  # calls __len__
assert Box([1])
assert Box.calls == 2
```

## イテレータとジェネレータ

ジェネレータは、`__len__` を持たないイテレータと同様に、自分がいくつ要素を生成するかを知らないので、`len()` は `TypeError` を送出します。要素を数えるとそれらは消費され、O(n) かかります。`operator.length_hint()` は反復せずに問い合わせます。組み込みのコンテナに対するイテレータでは残りの正確な個数を、ジェネレータでは `default` を返します。

```python
import operator

gen = (x * x for x in range(5))
try:
    len(gen)
except TypeError as error:
    assert "has no len()" in str(error)
else:
    raise AssertionError("expected TypeError")

assert operator.length_hint(gen, -1) == -1  # O(1) - a generator gives no hint
assert sum(1 for _ in gen) == 5  # O(n) - and the generator is now exhausted
assert list(gen) == []

it = iter([10, 20, 30])
next(it)
assert operator.length_hint(it) == 2  # O(1)
assert list(it) == [20, 30]  # nothing was consumed
```

## ChainMap

`ChainMap` は要素数を保存していません。`len()` を呼ぶたびにすべてのマップのキーから集合を作るので、すべてのマップとそのすべてのキーに比例するコストがかかり、複数のマップにあるキーは一度だけ数えられます。

```python
from collections import ChainMap

defaults = {"color": "red", "size": 10}
overrides = {"color": "blue"}
settings = ChainMap(overrides, defaults)

assert len(settings) == 2  # O(m + t) - "color" is in both maps
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- 組み込みのコンテナに対しては、ループの条件の中も含めて `len()` を気軽に呼んでください。O(1) です
- 空かどうかの判定には `if container:` を使ってください。組み込みのコンテナでは O(1) です
- 独自のコンテナでは個数を保持するか組み込みのコンテナに委ねて、`__len__` を O(1) にしてください
- 組み込みのコンテナのイテレータを消費せずにバッファの大きさを決めるには `operator.length_hint()` を使ってください

❌ **避けるべきこと**:

- 数えるためだけの `len(list(iterator))`: O(n) のリストを作ります。`sum(1 for _ in iterator)` は
  O(1) の空間で数えますが、どちらの場合もイテレータは消費されます
- 反復する `__len__`: クラスに `__bool__` がなければ `if obj:` もそれを呼び出します
- ループの中で `ChainMap` に `len()` を呼ぶこと: 呼び出しのたびにすべてのマップを走査します

## バージョン別の注記

- **Python 3.15+**: `frozendict` に対する `len()` は O(1) です

## 関連する関数

- **[bool()](bool_func.md)** - 真偽値の判定は `__len__` にフォールバックします
- **[iter()](iter.md)** - ジェネレータとほとんどのイテレータには長さがありません
- **[range](range.md)** - range は生成時に長さを計算します
- **[sum()](sum.md)** - イテレータの要素を数える
- **[collections](../stdlib/collections.md)** - `deque`、`Counter`、`ChainMap`
- **[operator](../stdlib/operator.md)** - イテレータ向けの `length_hint()`
