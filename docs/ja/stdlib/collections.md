---
source_sha: 45e6ee6587007e1eab2d114700afa7e63063edb6439cf6702f07a5f279051faf
translated: machine
---

# collections モジュールの計算量

`collections` モジュールは、特定の用途に最適化された専用のデータ構造を提供します。

## deque

操作、計算量、使用例は [deque](deque.md) を参照してください。

## DefaultDict

操作、計算量、使用例は [defaultdict](defaultdict.md) を参照してください。

## Counter

操作、計算量、使用例は [Counter](counter.md) を参照してください。

## NamedTuple

操作、計算量、使用例は [namedtuple](namedtuple.md) を参照してください。

## OrderedDict

操作、計算量、使用例は [OrderedDict](ordereddict.md) を参照してください。

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
