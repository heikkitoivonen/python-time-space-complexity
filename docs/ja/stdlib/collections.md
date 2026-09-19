---
source_sha: f5c4b3c5bd9a612e361874983042cd25d27aa989a7e7b47532e46516d57e6430
translated: machine
---

# collections モジュールの計算量

`collections` モジュールは、`dict`、`list`、`str`、`tuple` を特化させたコンテナ型を提供します。
そのうち 5 つには専用のページがあり（下にリンクがあります）、`collections.abc` の抽象基底クラスにも
専用のページがあります。このページの残りの部分では、マッピングを統合せずにリストを順に検索する
`ChainMap` と、素の `dict`、`list`、`str` を `data` 属性に保持して各操作をそれに転送する
`UserDict`、`UserList`、`UserString` を扱います。

## deque

操作、計算量、例については [deque](deque.md) を参照してください。

## defaultdict

操作、計算量、例については [defaultdict](defaultdict.md) を参照してください。

## Counter

操作、計算量、例については [Counter](counter.md) を参照してください。

## namedtuple

操作、計算量、例については [namedtuple](namedtuple.md) を参照してください。

## OrderedDict

操作、計算量、例については [OrderedDict](ordereddict.md) を参照してください。

## collections.abc

抽象基底クラスとそのミックスインメソッドのコストについては [collections.abc](collections.abc.md) を
参照してください。`ChainMap` とラッパーが自身で定義していないものはすべてこれらのミックスインに
由来し、ミックスインはラッパー自身の `__getitem__`、`__iter__`、`__setitem__` を使って書かれているため、
それらのいずれかをオーバーライドしたサブクラスは、ミックスインの各ステップでその代償を払います。

## サイズ変数

`ChainMap` では、`n` はマップの数、`i` はキーを保持する最初のマップの位置（ミスの場合は `n`）、
`N` は全マップにわたるエントリの総数、`m` は `maps[0]` のエントリ数です。ラッパーでは `n` は
`len(wrapper)`、`d` は以前の削除が辞書のテーブルに残したスロット数です。全体を通して `k` は
相手オペランドのサイズ、または与えられた項目の数です。キーのハッシュ化と比較は O(1) とし、
`ChainMap` の行はマップが辞書であることを前提とし、`data` に転送される操作のコストは
[dict](../builtins/dict.md)、[list](../builtins/list.md)、[str](../builtins/str.md) の各ページに
書かれているとおりです。

## 計算量リファレンス

### ChainMap

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `collections.ChainMap(*maps)` | O(n) | O(n) | マップをリストに保持します。何もコピーも統合もされないため、いずれかのマップへの後の変更がそのまま見えます |
| `ChainMap.maps` | O(1) | O(1) | リストそのもの。検索順を変えるには並べ替えるか拡張します |
| `cm[key]` | O(i) | O(1) | キーを持つマップが見つかるまで順に試します。ミスは n 個すべてを試して `KeyError` を送出します |
| `key in cm` | O(i) | O(1) | 同じ検索です |
| `cm.get(key, default=None)` | O(i) | O(1) | ヒット時は 2 回検索します。`in` のために 1 回、値のために 1 回です |
| `cm[key] = value`, `del cm[key]`, `cm.pop(key)`, `cm.popitem()` | O(1) | O(1) | `maps[0]` のみ。後ろのマップにあるキーの削除は `KeyError` を送出します |
| `cm.update(other)`, `cm \|= other` | O(k) | O(k) | `maps[0]` に書き込みます |
| `cm.setdefault(key, default=None)` | O(i) | O(1) | どのマップで見つかった値でも返します。書き込むのはミスのときだけで、書き込み先は `maps[0]` です |
| `cm.clear()` | O(m) | O(1) | `maps[0]` だけを空にします |
| `bool(cm)` | O(n) | O(1) | 最初の空でないマップで止まります。空のマップだけのチェーンはすべてを調べます |
| `len(cm)` | O(n + N) | O(n + N) | 重複を除いて数えるために、すべてのキーの集合を構築します。空のマップも含めてすべてのマップを訪れます |
| `cm.keys()`, `cm.items()`, `cm.values()` | O(1) | O(1) | チェーンに対するビュー。コストは反復時に支払われます |
| `cm` または `cm.keys()` の反復 | O(n + N) | O(N) | 最初のキーを返す前に、すべてのキーの辞書を構築します。最後のマップのキー、次に前のマップごとの新しいキーの順です |
| `cm.items()` または `cm.values()` の反復, `dict(cm)` | O(n + N·n) | O(N) | キーの走査に加えて、各キーに対して `cm[key]` を行い、チェーンを再び検索します |
| `cm == other` | O(n + N·n + k) | O(N + k) | 両辺を辞書に平坦化してから比較します |
| `cm.new_child(m=None, **kwargs)` | O(n + k) | O(n + k) | 既存のマップをすべて共有し、`m` を先頭に置いた新しい `ChainMap`。両方が与えられた場合、キーワード引数は `m` に書き込まれ、そうでなければ新しい辞書に書き込まれます |
| `ChainMap.parents` | O(n) | O(n) | `maps[1:]` に対する新しい `ChainMap`。マップは共有され、リストは共有されません |
| `cm.copy()` | O(m + n) | O(m + n) | `maps[0]` をコピーし、残りは共有します |
| `ChainMap.fromkeys(iterable, value=None)` | O(k) | O(k) | 1 つのマップからなるチェーンの下の 1 つの辞書 |
| `cm \| other` | O(m + n + k) | O(m + n + k) | `copy()` してから、コピーの最初のマップに `other` を書き込みます |
| `other \| cm` | O(n + N + k) | O(N + k) | すべてのエントリを平坦化して保持する 1 マップの `ChainMap`。層は失われます |

### UserDict

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `collections.UserDict(dict=None, /, **kwargs)` | O(k) | O(k) | `update()` を通じて `data` を埋めます。項目ごとに 1 回の `__setitem__` 呼び出し |
| `UserDict.data` | O(1) | O(1) | 素の辞書。ラッパーとそのミックスインを迂回するには、これを直接操作します |
| `ud[key]`, `ud[key] = value`, `del ud[key]`, `key in ud`, `len(ud)` | O(1) | O(1) | 転送されます。`ud[key]` は、サブクラスの `__missing__` が動けるように先にメンバーシップを調べます |
| `ud.get(key, default=None)` | O(1) | O(1) | Python 3.12+: `__missing__` を呼び出しません。3.12 より前は呼び出していました |
| `ud.keys()`, `ud.items()`, `ud.values()` | O(1) | O(1) | ラッパーへの参照を保持するビュー |
| `ud` または `ud.keys()` の反復 | O(n) | O(1) | 辞書自身の反復 |
| `ud.items()` または `ud.values()` の反復 | O(n) | O(1) | キーごとに 1 回の `ud[key]` |
| `ud.update(other)` | O(k) | O(1) | 項目ごとに 1 回の `__setitem__` 呼び出し |
| `ud \|= other` | O(k) | O(1) | `data` に対する 1 回の `dict.update` |
| `ud \| other` | O(n + k) | O(n + k) | 2 つの辞書をマージし、その結果から新しいラッパーを構築するため、すべての項目が再び `__setitem__` を通ります |
| `ud.copy()` | O(n) | O(n) | 素の `UserDict` は `data` をコピーします。サブクラスは浅くコピーされ、その後 `update()` で埋め直されます |
| `UserDict.fromkeys(iterable, value=None)` | O(k) | O(k) | キーごとに 1 回の `__setitem__` 呼び出し |
| `ud.pop(key)`, `ud.setdefault(key, default=None)` | O(1) | O(1) | `ud[key]` の後に `del ud[key]` または `ud[key] = default` |
| `ud.popitem()` | O(d) | O(1) | 反復順で最初のキーを取り除きます。d はその前に削除されたエントリ数で、新しいイテレータはそれらを読み飛ばさなければなりません |
| `ud.clear()` | O(n·(n + d)) | O(1) | 空になるまで `popitem()` を繰り返し、各呼び出しは前の呼び出しが空にしたスロットをすべて読み飛ばします。`ud.data.clear()` は O(n) です |
| `ud == other` | O(n + k) | O(n + k) | `other` がすでに辞書であっても、両辺を辞書に平坦化してから比較します |

### UserList

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `collections.UserList(initlist=None)` | O(k) | O(k) | リストまたは別の `UserList` をコピーします。その他のイテラブルは新しいリストへ消費されます |
| `UserList.data` | O(1) | O(1) | 素のリスト |
| `ul[i]`, `ul[i] = value`, `len(ul)` | O(1) | O(1) | 転送されます |
| `ul[i:j]` | O(j - i) | O(j - i) | `__init__` を通して構築された `type(ul)` を返します。`copy()`、`+`、`*` も同様です |
| `ul.append(x)` | O(1) 償却 | O(1) | 転送されます |
| `ul.insert(i, x)`, `del ul[i]`, `ul.pop(i=-1)`, `ul.remove(x)` | O(n) | O(1) | `i` より後ろの項目がずれるため、末尾からの `pop()` は O(1) です |
| `ul.extend(other)`, `ul += other` | O(k) | O(k) | `+=` はリスト以外のイテラブルを拡張前にリストへコピーします |
| `ul + other`, `ul * k` | O(n + k), O(n·k) | O(n + k), O(n·k) | `type(ul)` の新しいインスタンス。`other` はリスト、`UserList`、任意のイテラブルのいずれでも構いません |
| `ul *= k` | O(n·k) | O(n·k) | インプレース |
| `x in ul`, `ul.count(x)`, `ul.index(x)`, `ul.reverse()` | O(n) | O(1) | 転送されます |
| `ul.sort(*, key=None, reverse=False)` | O(n log n) | O(n) | `data` に対する `list.sort` |
| `ul.clear()`, `ul.copy()` | O(n) | O(1), O(n) | `copy()` は `type(ul)(ul)` です |
| `ul` または `reversed(ul)` の反復 | O(n) | O(1) | `Sequence` のミックスイン。項目ごとに 1 回の `ul[i]` 呼び出しで、`iter()` は `ul[n]` の `IndexError` で終わります |
| `ul == other`, `ul < other` | O(min(n, k)) | O(1) | `data` を相手のリスト、または相手の `UserList` の `data` と比較します |

### UserString

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `collections.UserString(seq)` | O(1) | O(1) | `str` はコピーされずそのまま保持されます。それ以外はまず `str()` を通り、その変換のコストがかかります |
| `UserString.data` | O(1) | O(1) | 素の文字列 |
| `us[i]`, `us[i:j]` | O(1), O(j - i) | O(1), O(j - i) | 文字またはスライスを包む新しい `type(us)`。`str` になることはありません |
| `us` の反復 | O(n) | O(1) | `Sequence` のミックスイン。文字ごとに 1 回の `us[i]` で、各文字が新しいラッパーとして届きます |
| `len(us)`, `str(us)` | O(1) | O(1) | `str(us)` は `data` そのものです |
| `hash(us)` | O(n) | O(1) | `data` のハッシュ |
| `sub in us`, `us.count(sub)`, `us.find(sub)`, `us.rfind(sub)`, `us.index(sub)`, `us.rindex(sub)`, `us.startswith(prefix)`, `us.endswith(suffix)` | O(n + k) 平均 | O(1) | `str` の検索の平均ケース。結果は素の `int` または `bool` です |
| `us.capitalize()`, `us.casefold()`, `us.center(width)`, `us.expandtabs()`, `us.ljust(width)`, `us.lower()`, `us.lstrip()`, `us.removeprefix(prefix)`, `us.removesuffix(suffix)`, `us.replace(old, new)`, `us.rjust(width)`, `us.rstrip()`, `us.strip()`, `us.swapcase()`, `us.title()`, `us.translate(table)`, `us.upper()`, `us.zfill(width)` | O(n + 出力) | O(n + 出力) | 出力と同じ長さの新しい `str` を `type(us)` で包みます。大文字小文字変換と strip 系は n、パディング系は `width`、置換や変換テーブルはその生成結果の長さです |
| `us.split()`, `us.rsplit()`, `us.splitlines()`, `us.partition(sep)`, `us.rpartition(sep)` | O(n) | O(n) | `str` を含む素の `list` または `tuple`。ラッパー型は失われます |
| `us.join(iterable)` | O(k + 出力) | O(k + 出力) | 素の `str`。k は結合する文字列の数で、すでにシーケンスでなければ先にリストに集められます |
| `us.encode()` | O(n) | O(n) | 素の `bytes` |
| `us.format(*args, **kwargs)`, `us.format_map(mapping)` | O(n + 出力) | O(n + 出力) | 素の `str`。テンプレート全体が走査されます |
| `us.isalnum()`, `us.isalpha()`, `us.isdecimal()`, `us.isdigit()`, `us.isidentifier()`, `us.islower()`, `us.isnumeric()`, `us.isprintable()`, `us.isspace()`, `us.istitle()`, `us.isupper()` | O(n) | O(1) | 答えが決まる最初の文字で止まります |
| `us.isascii()` | O(1) | O(1) | `str` が保持するフラグを読みます |
| `us + other`, `other + us` | O(n + k) | O(n + k) | 新しいラッパー。`str` でないオペランドは `str()` を通ります |
| `us * k`, `us % args` | O(n·k), O(n + 出力) | O(n·k), O(n + 出力) | 新しいラッパー |
| `us == other`, `us < other` | O(min(n, k)) | O(1) | `data` を比較します。`other` は `str` でも `UserString` でも構いません |
| `UserString.maketrans(x, y=None, z=None)` | O(k) | O(k) | `str.maketrans` そのもの |
| `int(us)` | O(n²) | O(n) | `data` に対する `int()` なので、[int](../builtins/int.md) ページの 10 進数桁数の上限が適用されます |
| `float(us)`, `complex(us)` | O(n) | O(n) | `data` の変換 |

## ChainMap による階層化

### 検索はチェーンをたどる

`ChainMap` はコピーではなく参照を保持します。すべての読み取りはマップを順に試し、最初のヒットで
止まるため、最後のマップにあるキーは n 回の検索を要し、ミスは常にそうなります。書き込みは
`maps[0]` だけに行われ、これがチェーンをスコープに役立てる理由です。子スコープは親に触れることなく
親を覆い隠します。

```python
from collections import ChainMap

defaults = {"timeout": 30, "retries": 3}
user = {"timeout": 60}
config = ChainMap(user, defaults)  # O(n) - two references, nothing copied

assert config["timeout"] == 60  # O(i) - found in the first map
assert config["retries"] == 3  # O(i) - found in the second
assert config.get("colour", "none") == "none"  # O(n) - a miss checks every map

config["retries"] = 5  # O(1) - into maps[0]
assert user == {"timeout": 60, "retries": 5}
assert defaults["retries"] == 3  # the parent is untouched

del config["timeout"]  # O(1) - maps[0] has it
try:
    del config["timeout"]  # now only defaults has it
except KeyError as error:
    assert "first mapping" in str(error)
else:
    raise AssertionError("a key in a later map was deleted")

# Scopes: new_child() puts a fresh map in front, parents drops the front one
scope = config.new_child()  # O(n) - shares every map
scope["timeout"] = 1
assert scope["timeout"] == 1 and config["timeout"] == 30
assert scope.parents.maps == config.maps  # O(n) - a new list over the same maps
```

### 数えることと反復はすべてのキーのコストがかかる

`len()` に近道はありません。チェーンは重複を除いた数を知るためにすべてのキーの集合を構築し、
反復は最初のキーを返す前にすべてのキーの辞書を構築します。どちらも、それ以外は何も保持しない
構造に対してすべてのマップとすべてのエントリを訪れる O(n + N) なので、大きなマップのチェーンを
ループ内で測ったり反復したりすべきではありません。反復順は、最後のマップのキー、次に前の各マップのまだ見ていないキーです。

```python
from collections import ChainMap

first = {"a": 1, "b": 2}
second = {"c": 3, "a": 0}
chain = ChainMap(first, second)

assert len(chain) == 3  # O(n + N) - a set of every key, counted once each
assert list(chain) == ["c", "a", "b"]  # O(n + N) - built before the first key is yielded
assert dict(chain) == {"a": 1, "b": 2, "c": 3}  # O(n + N·n) - each key searched again

# Flattening through | keeps the values the chain would return, but not the layers
flat = {"z": 26} | chain  # O(n + N + k)
assert flat.maps == [{"z": 26, "c": 3, "a": 1, "b": 2}]
```

## UserDict、UserList、UserString によるラップ

### フックは項目ごとに 1 回動く

ラッパーはサブクラス化されるために存在します。オーバーライドされた `UserDict.__setitem__` は、
構築、`update()`、`fromkeys()`、`|` を見ることができ、これらはすべて項目ごとにそれを通ります。
`dict` をサブクラス化した場合はそうなりません。`|=` と `data` に転送されるメソッドはそれを
迂回します。`UserList` や `UserString` でオーバーライドされた `__getitem__` は反復のすべての
ステップを見ます。反復は内部オブジェクトのイテレータではなく、インデックスごとにそれを通るからです。

```python
from collections import UserDict, UserList

class Recording(UserDict):
    def __init__(self, *args, **kwargs):
        self.writes = 0
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        self.writes += 1
        super().__setitem__(key, value)

recorded = Recording({"a": 1, "b": 2, "c": 3})  # O(k) - one __setitem__ per item
assert recorded.writes == 3

recorded.update(d=4)  # O(k) - the mixin loop, one __setitem__ per item
assert recorded.writes == 4

merged = recorded | {"e": 5}  # O(n + k) - the merged dict is fed back through __setitem__
assert merged.writes == 5
assert recorded.writes == 4

class Indexed(UserList):
    reads = 0

    def __getitem__(self, index):
        Indexed.reads += 1
        return super().__getitem__(index)

items = Indexed([10, 20, 30])
assert list(items) == [10, 20, 30]  # O(n) - n + 1 __getitem__ calls, the last raising IndexError
assert Indexed.reads == 4
```

### UserDict を空にする

`UserDict` は `clear()`、`popitem()`、`pop()` を定義しておらず、`MutableMapping` から継承します。
その `popitem()` は新しいイテレータが返す最初のキーを取り、辞書のイテレータは以前の削除で空に
なったスロットをすべて読み飛ばさなければならないため、`popitem()` は O(d) かかり、
`clear()` で辞書全体を空にするには O(n·(n + d)) かかります。`data` 辞書を直接クリアしてください。

```python
from collections import UserDict

wrapped = UserDict({"a": 1, "b": 2, "c": 3})

assert wrapped.popitem() == ("a", 1)  # O(d) - the first key still present
assert wrapped.popitem() == ("b", 2)

wrapped.data.clear()  # O(n) - the dict's own clear
assert len(wrapped) == 0

wrapped.update(zip("xyz", range(3)))
wrapped.clear()  # O(n·(n + d)) - popitem() until empty
assert len(wrapped) == 0
```

### ラッパーはラッパーとして返ってくる

`upper()` や `strip()` のようにテキストを変換する `UserString` のメソッドは新しい `type(us)` を
返し、インデックス参照と反復も同様なので、`UserString` に対するループは文字ごとに 1 つのラッパーを
割り当てます。`split()` や `partition()` のようにテキストのコンテナを返すメソッドは、素の `list`
または `tuple` に入った素の `str` を返し、`join()`、`format()`、`format_map()` は素の `str` を
返します。`UserList` のスライスと算術も `__init__` を
通して構築された `type(ul)` を返すため、追加の必須引数を持つサブクラスのコンストラクタはスライスを
壊します。

```python
from collections import UserString

source = "abc"
text = UserString(source)  # O(1) - the str is held, not copied
assert text.data is source

assert type(text.upper()) is UserString  # O(n) - a new str, wrapped
assert type(text[0]) is UserString  # O(1) - even one character is wrapped
assert all(type(char) is UserString for char in text)  # O(n) - one wrapper per character

assert type(text.split()) is list and type(text.split()[0]) is str  # O(n) - plain str inside
assert type(text.join(["x", "y"])) is str  # O(output) - plain str
assert type(text.encode()) is bytes
assert text.count("b") == 1 and text.find("z") == -1  # O(n + k) - plain int results
```

## よくあるパターン

### 上書き付きの設定

```python
from collections import ChainMap

defaults = {"host": "localhost", "port": 8000, "debug": False}
environment = {"port": 8080}
command_line = {"debug": True}

settings = ChainMap(command_line, environment, defaults)  # O(n) - three references

assert settings["port"] == 8080  # O(i) - the environment wins over the default
assert settings["debug"] is True  # O(i) - the command line wins over everything
assert settings["host"] == "localhost"  # O(n) - found in the last map

# Read the resolved settings once, then work from the dict
resolved = dict(settings)  # O(n + N·n) - once, not on every read
assert resolved == {"host": "localhost", "port": 8080, "debug": True}
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- `ChainMap` は短く保つ。すべてのミス、デフォルトに落ちる `get()`、最後のマップにあるキーの読み取りは、マップごとに 1 回の検索を要する
- ループ内でチェーンを読むときは `dict(chain)` で一度だけ平坦化し、マップごとの検索を読み取りごとではなくキーごとに 1 回にする
- `UserDict` は `data.clear()` でクリアする。継承された `clear()` はエントリ数とその前に削除されたスロット数について 2 乗のコストがかかる
- ホットループがサブクラスのフックを必要としないなら、`ud.data`、`ul.data`、`us.data` を使う

❌ **避ける**:

- ループ内での `ChainMap` に対する `len()` や反復 - 呼び出しごとにすべてのキーの集合や辞書を作り直す
- ホットパスでの `UserDict` の `==` による比較。ミックスインは毎回両辺を新しい辞書に平坦化する
- `UserString` を 1 文字ずつ反復すること。各文字が新しいラッパーオブジェクトになる
- `__init__` に追加の引数が必要な `UserList` のサブクラス。スライス、`copy()`、`+`、`*` はすべてそれを通して構築する

## バージョンに関する注意

- **Python 3.12+**: `UserDict.get()` は、`__missing__` を呼び出さずに存在しないキーに対してデフォルトを返す。3.12 より前は継承された `Mapping.get()` が `__getitem__` を経由し、それを呼び出していた
- **すべての Python 3**: `ChainMap` に対する `len()` と反復は、すべてのマップのすべてのエントリのコストがかかる。チェーンについて何もキャッシュされない

## 関連モジュール

- **[dict](../builtins/dict.md)** - 転送される `UserDict` の操作のコスト
- **[list](../builtins/list.md)** - 転送される `UserList` の操作のコスト
- **[str](../builtins/str.md)** - 転送される `UserString` の操作のコスト
