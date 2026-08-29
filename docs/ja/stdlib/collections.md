---
source_sha: f99a7f1db066324adce1ef1c4d66432c20d2c2889467ceb9f2910ca4212c8768
translated: machine
---

# collections モジュールの計算量

`collections` モジュールは、特定の用途に最適化された専用のデータ構造を提供します。

## deque

### 時間計算量

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `append(x)` | O(1) | O(1) | 右端に追加する |
| `appendleft(x)` | O(1) | O(1) | 左端に追加する |
| `pop()` | O(1) | O(1) | 右端から取り除く |
| `popleft()` | O(1) | O(1) | 左端から取り除く |
| `access[i]` | 両端は O(1)、中央は O(n) | O(1) | 両端（d[0]、d[-1]）は O(1)。ブロック構造のため中央の要素は O(n) |
| `extend(iterable)` | O(k) | O(k) | k はイテラブルの長さ |
| `extendleft(iterable)` | O(k) | O(k) | k はイテラブルの長さ。注意: 順序が反転する |
| `rotate(n)` | O(k) | O(1) | k = min(n, len(d) - n) |
| `clear()` | O(n) | O(1) | すべての要素を取り除く |
| `copy()` | O(n) | O(n) | 浅いコピー |
| `count(x)` | O(n) | O(1) | x の出現回数を数える |
| `index(x)` | O(n) | O(1) | x が最初に現れる位置を求める |
| `insert(i, x)` | O(n) | O(1) | 位置 i に x を挿入する |
| `remove(x)` | O(n) | O(1) | 最初に現れる x を取り除く |
| `reverse()` | O(n) | O(1) | その場で反転する |
| `in`（メンバーシップ） | O(n) | O(1) | 線形探索 |

### 属性

| 属性 | 備考 |
|-----------|-------|
| `maxlen` | 最大の大きさ（上限がなければ None）、読み取り専用 |

### 空間計算量

- 格納: n 要素に対して O(n)
- 操作: append と pop は O(1)

### 使いどころ

```python
from collections import deque

# Process items from both ends - very efficient
queue = deque([1, 2, 3])
queue.appendleft(0)  # O(1) - add to front
queue.pop()  # O(1) - remove from back

# Much faster than list for this pattern:
# list.insert(0, x) is O(n)
# list.pop(0) is O(n)
```

## DefaultDict

### 時間計算量

`dict` と同じです。

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `d[key]` | 平均 O(1) | O(1) | キーがなければ既定値を返す。ハッシュ衝突により最悪は O(n) |
| `d[key] = value` | 平均 O(1) | O(1) | ハッシュ衝突により最悪は O(n) |
| `del d[key]` | 平均 O(1) | O(1) | ハッシュ衝突により最悪は O(n) |
| `copy()` | O(n) | O(n) | 浅いコピー |
| そのほかの dict の操作 | dict と同じ | - | |

### 属性

| 属性 | 備考 |
|-----------|-------|
| `default_factory` | 既定値を返す呼び出し可能オブジェクト。None でもよい |

### 空間計算量

- n 組のキーと値に対して O(n)
- ファクトリはキーにアクセスしたときだけ呼ばれる

### 使いどころ

```python
from collections import defaultdict

# Avoid: manual checking - a membership test, then a store, then the append
groups = {}
if 'key' not in groups:
    groups['key'] = []
groups['key'].append('value')

# Better: the factory supplies the list - O(1) avg, one lookup
data = defaultdict(list)
data['key'].append('value')

# Avoid: clunky dict.get()
counts = {}
counts['key'] = counts.get('key', 0) + 1  # O(1) avg, a get and a set spelled out

# Better: defaultdict with int
tally = defaultdict(int)
tally['key'] += 1  # O(1) avg - still a get plus a set, but one statement
                   # and no default to pass in
```

## Counter

### 時間計算量

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `Counter(iterable)` | O(n) | O(k) | n はイテラブルの長さ、k は異なる要素の個数 |
| `c[item]` | 平均 O(1) | O(1) | なければ 0 を返す。ハッシュ衝突により最悪は O(n) |
| `c.most_common(k)` | O(n log k) | O(k) | n は `len(c)`、すなわち異なるキーの数。`k=1` は `max()`、`k >= len(c)` は `sorted()` にフォールバックし、その間は大きさ k のヒープを保つ。それが全体のソートより速いかは件数の分布による。ランダムや Zipf 的なデータでは明確に速く、件数が反復順に増加する場合は要素ごとにヒープ置換が起きるため遅くなる |
| `c.update(iterable)` | O(n) | O(k) | n はイテラブルの長さ |
| `c.subtract(iterable)` | O(n) | O(1) | 個数を引く。負の値も保持する |
| `c.total()` | O(n) | O(1) | すべての個数の合計（Python 3.10+） |
| `c.elements()` | 生成は O(1)、反復は O(total) | O(1) | 各要素をその個数だけ繰り返すイテレータ |
| `c.copy()` | O(n) | O(n) | 浅いコピー |
| `c.fromkeys(iterable)` | N/A | - | Counter では役に立たない。dict から継承しているだけ |
| `c + c2` | O(n) | O(n) | カウンタを合成する。正の個数だけ残る |
| `c - c2` | O(n) | O(n) | 引き算する。正の個数だけ残る |

### 使いどころ

```python
from collections import Counter

# Count items - O(n) for n items
words = ['apple', 'banana', 'apple', 'cherry', 'apple']
c = Counter(words)
# Counter({'apple': 3, 'banana': 1, 'cherry': 1})

# Most common items - O(n log k) for k items, n = len(c). Whether that beats
# sorting everything depends on the counts; see the note in the table above
top_3 = c.most_common(3)  # [('apple', 3), ('banana', 1), ('cherry', 1)]

# Arithmetic - O(n) over the combined keys
c1 = Counter('aab')
c2 = Counter('abc')
c1 + c2  # Counter({'a': 3, 'b': 2, 'c': 1})
```

## NamedTuple

### 時間計算量

すべての操作でタプルと同じです。

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| 生成 | O(1) | O(1) | フィールド数は固定 |
| 添字によるアクセス | O(1) | O(1) | タプルと同じ |
| 名前によるアクセス | O(1) | O(1) | タプルと同じ |
| 反復 | O(n) | O(1) | n はフィールド数 |

### 使いどころ

```python
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])
p = Point(11, y=22)

# Better than plain tuple
print(p.x)  # More readable than p[0]

# Create from dict
d = {'x': 1, 'y': 2}
p = Point(**d)

# Replace values
p2 = p._replace(x=5)
```

## OrderedDict

### 時間計算量

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| dict と同じ | O(1) | O(1) | dict のすべての操作 |
| `move_to_end(key)` | O(1) | O(1) | キーを末尾へ移す |

### 注記

- **Python 3.6+**: 通常の `dict` が順序を保つため、`OrderedDict` が主に役立つのは次の場合です。

  - 古いコードとの互換性
  - 並べ替えのための `move_to_end()` メソッド
  - コード上で意図を明示したいとき

```python
from collections import OrderedDict

# Useful method: move_to_end()
od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
od.move_to_end('a')  # O(1) - moves 'a' to end
```

## ChainMap

### 時間計算量

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `access[key]` | O(n) | O(1) | n はマップの個数。見つかるまで探す |
| `set[key]` | 平均 O(1) | O(1) | 先頭のマップに設定する。先頭のマップの大きさを m として最悪は O(m) |
| `del[key]` | 平均 O(1) | O(1) | 先頭のマップから削除する。先頭のマップの大きさを m として最悪は O(m) |
| `len()` | O(N) | O(N) | N はすべてのマップのキーの総数。内部で和集合を作る |
| `in` | O(n) | O(1) | すべてのマップを調べる |

### 使いどころ

```python
from collections import ChainMap

# Layer multiple dicts
defaults = {'timeout': 30, 'retries': 3}
user_config = {'timeout': 60}

config = ChainMap(user_config, defaults)
print(config['timeout'])  # 60 (from user_config)
print(config['retries'])  # 3 (from defaults)

# View layered configuration without merging
```

## 性能の比較

| 操作 | dict | defaultdict | Counter | OrderedDict |
|-----------|------|-------------|---------|------------|
| `d[key]` | O(1) | O(1) | O(1) | O(1) |
| `d[key] = value` | O(1) | O(1) | O(1) | O(1) |
| 固有のメソッド | - | `__missing__` | `most_common()` | `move_to_end()` |
| メモリ | 基準 | わずかに増 | カウンタの分だけ増 | 順序の管理の分だけ増 |

## UserDict

`UserDict` は標準の dict を包み、利用者がクラスとして拡張できるようにします。

### 時間計算量

ほとんどの操作は `dict` と同じです。

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `d[key]` | 平均 O(1) | O(1) | ハッシュ衝突により最悪は O(n) |
| `d[key] = value` | 平均 O(1) | O(1) | 最悪は O(n) |
| `del d[key]` | 平均 O(1) | O(1) | 最悪は O(n) |
| 反復 | O(n) | O(1) | n は要素の個数 |

## UserList

`UserList` は標準の list を包み、利用者がクラスとして拡張できるようにします。

### 時間計算量

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| 添字アクセス | O(1) | O(1) | 添字による参照 |
| 末尾への追加 | 償却 O(1) | O(1) | リサイズ時は最悪 O(n) |
| 挿入・削除 | O(n) | O(1) | 要素をずらす |
| 反復 | O(n) | O(1) | n はリストの長さ |

## UserString

`UserString` は標準の文字列を包み、利用者がクラスとして拡張できるようにします。

### 時間計算量

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| 添字アクセス | O(1) | O(1) | 添字による参照 |
| 連結 | O(n) | O(n) | n は全体の長さ |
| スライス | O(k) | O(k) | k はスライスの長さ |
| 反復 | O(n) | O(1) | n は長さ |

## 関連するドキュメント

- [組み込みの dict](../builtins/dict.md)
- [組み込みの tuple](../builtins/tuple.md)
- [heapq モジュール](heapq.md)
