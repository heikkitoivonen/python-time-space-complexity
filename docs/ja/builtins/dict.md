---
source_sha: 8fd3d66178b61ce76428fd4d9d654b6858f39d3c2870bb746da072fd9957bab2
translated: machine
---

# 辞書操作の計算量

`dict` 型はキーと値の組を格納する可変のマッピングです。CPython ではハッシュテーブルとして実装されています。

`n` は辞書の要素数、`k` はもう一方のオペランドまたはイテラブルの要素数です。キーのハッシュ計算と比較は O(1) とみなします。

## 計算量リファレンス

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len()` | O(1) | O(1) | 保持している個数を返す |
| `access[key]` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ探索、最悪は衝突が起きた場合 |
| `set[key] = value` | 償却 O(1) | O(1) | ハッシュ挿入、リサイズを誘発することがある |
| `del[key]` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ削除 |
| `key in dict` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ探索 |
| `get(key)` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ探索 |
| `pop(key)` | 平均 O(1)、最悪 O(n) | O(1) | ハッシュ削除 |
| `clear()` | O(n) | O(1) | すべてのエントリを解放する必要がある |
| `keys()` | O(1) | O(1) | ビューオブジェクト（反復には O(n)） |
| `values()` | O(1) | O(1) | ビューオブジェクト（反復には O(n)） |
| `items()` | O(1) | O(1) | ビューオブジェクト（反復には O(n)） |
| `d` の反復 | O(n) | O(1) | 挿入順 |
| `copy()` | O(n) | O(n) | すべての組の浅いコピー |
| `update(other)`, `d \|= other` | O(k) | O(1) | k = len(other)、償却。これに `other` の反復コストが加わる。その場で変更する |
| `d \| other` | O(n + k) | O(n + k) | 新しい辞書。`d` をコピーしてから `other` で更新する |
| `setdefault(key, val)` | 平均 O(1) | O(1) | ハッシュ探索と挿入 |
| `fromkeys(keys)` | O(k) | O(k) | k = len(keys) |
| `popitem()` | O(1) | O(1) | 最後に挿入した組を取り除く（3.7 以降は LIFO） |

*注: 平均計算量 O(1) はハッシュがよく分散していることを前提としています。最悪計算量 O(n) は病的なハッシュ衝突が起きた場合に生じますが、Python のランダム化ハッシュのもとではめったに起こりません。*

要素を削除してもテーブルは縮小しません。大半の要素を削除した後も、テーブルを走査する操作（反復、`copy()`、`other.update(d)`、`|`、`==`、`dict(d)`）は、後の挿入でリサイズが起きるまで、辞書の以前のサイズに比例した時間がかかります。`len()` と検索は影響を受けません。

## 実装の詳細

### ハッシュテーブルの構造

CPython のハッシュテーブルは次のようになっています。

- **ハッシュ関数**: `str` と `bytes` には SipHash13（Python 3.11 以降の既定）、ほかの型は型ごとのハッシュを使う
- **衝突の処理**: 探査によるオープンアドレス法
- **成長の係数**: 負荷率を超えると約 2〜4 倍
- **Python 3.6（CPython）**: コンパクトな辞書が実装上の詳細として挿入順序を保つ

### ハッシュ衝突の影響

```python
# Best case: perfect hashing (O(1))
d = {i: i for i in range(1000)}
value = d[500]  # O(1)

# Worst case: hash collisions (degraded, but very rare)
# CPython mitigates this with randomized hashing
```

### 削除してもテーブルは縮小しない

`del` と `pop()` はテーブルを最大サイズのまま残すため、走査はかつて存在したすべてのスロットを訪れます。大半の要素を失った辞書に対しては `copy()` がコンパクトな辞書を作るので、その後の走査は再び安価になります。

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

### 挿入順序の保証

```python
# Python 3.7+ guarantees insertion order (language guarantee)
d = {}
d['a'] = 1
d['b'] = 2
d['c'] = 3
# Iteration order: a, b, c (guaranteed)
```

## バージョン別の注記

| バージョン | 変更点 |
|---------|--------|
| Python 3.6 | CPython のコンパクトな辞書が挿入順序を保つ（実装上の詳細） |
| Python 3.7+ | 挿入順序が言語仕様で保証される |
| Python 3.9+ | 辞書の結合・更新演算子（`\|`、`\|=`） |
| Python 3.10+ | 辞書に対するパターンマッチング |
| Python 3.11+ | キーがすべて Unicode 文字列の場合、サイズが 23% 小さくなる |
| Python 3.15+ | [`frozendict`](frozendict.md)：不変でハッシュ可能な辞書 |

## 実装ごとの比較

### CPython
標準的なハッシュテーブル実装で、高度に最適化されている。

### PyPy
計算量はほぼ同じで、JIT コンパイルによりさらに最適化される場合がある。

### Jython
下層で Java の HashMap を使うが、O(1) という特性は同じ。

### IronPython
CPython と同様のハッシュテーブル実装。

## ベストプラクティス

✅ **推奨**:

- キーと値の探索には辞書を使う
- 辞書内包表記を活用する: `{k: v for k, v in items}`
- 条件付きの挿入には `setdefault()` を使う

❌ **避けるべきこと**:

- 移植性のために、Python 3.7 未満で挿入順序に頼らない
- ハッシュ不可能な型（リスト、辞書、集合）をキーにする
- ハッシュ関数の質が悪いまま非常に大きな辞書を作る

## ハッシュ関数に関する注意

```python
# Hashable types work as keys
d = {
    (1, 2): 'tuple_key',
    'string': 'str_key',
    42: 'int_key',
    frozenset([1, 2]): 'frozen_key'
}

# Unhashable types will fail
# d[[1, 2]] = 'fails'  # TypeError
# d[{1, 2}] = 'fails'  # TypeError
```

## 関連する型

- **[集合](set.md)** - 順序を持たない重複のない要素
- **[frozendict](frozendict.md)** - 不変でハッシュ可能な辞書（Python 3.15+）
- **[Defaultdict](../stdlib/collections.md#defaultdict)** - 既定値を自動で用意する
- **[OrderedDict](../stdlib/collections.md#ordereddict)** - 明示的な順序付け（3.6 より前）
- **[ChainMap](../stdlib/collections.md#chainmap)** - 複数の辞書をまとめて見る

## さらに読む

- [CPython Internals: dict](https://zpoint.github.io/CPython-Internals/BasicObject/dict/dict.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython の辞書実装を掘り下げた解説
