---
source_sha: d68992f3f4de5abc5706af482d0525f0a95ba6718edc716dc1d6379f72e39aa0
translated: machine
---

# 文字列操作の計算量

`str` 型は Unicode 文字の不変なシーケンスです。CPython はどの文字列も 1 文字あたり固定の幅で格納し、その幅は最も幅の広い文字によって 1、2、4 バイトのいずれかに決まるため、添字アクセスは直接行われます。文字列は変更できないので、厳密に `str` 型である文字列をコピーすると、その文字列自身が返されます。

`n` は文字列の長さ、`m` は文字列引数（`sub`、`prefix`、`sep`、`old`）の長さ、`r` は結果の長さ、`k` は繰り返し回数、`w` は指定した幅、`c` は `chars` 引数の長さです。`i:j` はスライスの範囲で、負の値を正規化した後のものとして数えます。`start` と `end` 引数を渡すと、`n` は探索する範囲の長さになり、その範囲はコピーされずにその場で読まれます。`s` より狭い幅で格納された複数文字の引数（CJK 文字を含むテキスト中の ASCII の部分文字列など）は、まず `s` の幅にコピーされます。探索メソッドと `count()`、`replace()`、`split()`、`rsplit()`、`partition()`、`rpartition()` では、これに O(m) の追加の空間がかかります。

## 計算量リファレンス

### str

| 操作 | 時間 | 空間 | 備考 |
|-----------|------|-------|-------|
| `len(s)` | O(1) | O(1) | 長さは文字列に格納されており、数え直さない |
| `s[k]` | O(1) | O(1) | 添字による直接アクセス。結果は 1 文字の文字列 |
| `s[i:j]`（スライス） | O(j-i) | O(j-i) | ステップ付きなら O(r)。厳密な `str` の `s[:]` は `s` 自身を返す |
| `s[:]`, `str(s)`, `copy.copy(s)` | O(1) | O(1) | 厳密な `str` なら `s` 自身を返す。サブクラスのインスタンスは O(n) でコピーされる |
| `s + t`（連結） | O(n+len(t)) | O(n+len(t)) | 一方が空ならもう一方のオペランド自身を返す。ループ内で `+=` によって文字列を組み立てると最悪の場合 O(r²) |
| `s * k`（繰り返し） | O(nk) | O(nk) | k ≤ 0 なら空文字列。`s * 1` は `s` 自身を返す |
| `s == t` | O(n) | O(1) | 長さか文字の幅が異なる場合、または両方が同じオブジェクトの場合は O(1) |
| `s < t`, `<=`, `>`, `>=` | O(min(n, len(t))) | O(1) | 最初の異なる文字で止まる |
| `hash(s)` | 初回 O(n)、以降 O(1) | O(1) | 結果は文字列に保持される。別に作った等しい文字列は、自分の初回ハッシュ計算のコストを払う |
| `for c in s` | O(n) | O(1) | 1 ステップごとに 1 文字の文字列 |
| `sub in s`（部分文字列） | O(n) | O(1)、拡幅時 O(m) | 最悪の場合でも線形の前方探索。文字列より長い部分文字列はすぐに返る |
| **探索** ||||
| `find(sub, start, end)` | O(n) | O(1)、拡幅時 O(m) | 前方探索。n は探索する文字数 |
| `rfind(sub, start, end)` | 最悪 O(n·m) | O(1)、拡幅時 O(m) | 後方探索。典型的な入力では O(n) |
| `index(sub, start, end)` | O(n) | O(1)、拡幅時 O(m) | `find()` と同じだが、見つからないと `ValueError` を送出する |
| `rindex(sub, start, end)` | 最悪 O(n·m) | O(1)、拡幅時 O(m) | `rfind()` と同じだが、見つからないと `ValueError` を送出する |
| `count(sub, start, end)` | O(n) | O(1)、拡幅時 O(m) | 前方探索 |
| `startswith(prefix)` | O(m) | O(1) | 接頭辞の分だけを比較する |
| `endswith(suffix)` | O(m) | O(1) | 接尾辞の分だけを比較する |
| **置換・変換** ||||
| `replace(old, new)` | O(n + r) | O(r)、拡幅時 O(m) | `old` を前方探索する。`old` が現れなければ `s` 自身を返す |
| `translate(table)` | O(n + r) | O(n + r) | テーブルの探索 1 回を O(1) とみなす。より長い文字列への対応付けがあると r は n を超える |
| `str.maketrans(x, y, z)` | O(e) | O(e) | e は引数の文字数または辞書のエントリ数。静的メソッド |
| `expandtabs(tabsize)` | O(n + r) | O(r) | タブ 1 つごとに結果が最大 `tabsize` 文字増える。タブがなければ `s` 自身を返す |
| `removeprefix(prefix)` | O(n) | O(n) | `prefix` が一致すれば残りをコピーする。一致しなければ O(m) で `s` 自身を返す |
| `removesuffix(suffix)` | O(n) | O(n) | `suffix` が一致すれば残りをコピーする。一致しなければ O(m) で `s` 自身を返す |
| **分割・結合** ||||
| `split(sep)` | O(n) | O(n) | `sep` を前方探索する |
| `rsplit(sep)` | 最悪 O(n·m) | O(n) | `rfind()` と同じく後方へ探索する。`sep` なし、または 1 文字の `sep` なら O(n) |
| `splitlines()` | O(n) | O(n) | 行の境界で分割する |
| `partition(sep)` | O(n) | O(n) | 最初の `sep` を前方探索する |
| `rpartition(sep)` | 最悪 O(n·m) | O(n) | `rfind()` と同じく後方へ探索する |
| `sep.join(iterable)` | O(r + p) | O(r + p) | p は断片の数。リストでもタプルでもないイテラブルはまずリストに集められる。厳密な `str` の断片が 1 つだけなら、それ自身が返される |
| **大文字・小文字変換** ||||
| `upper()` | O(n) | O(n) | |
| `lower()` | O(n) | O(n) | |
| `capitalize()` | O(n) | O(n) | 先頭をタイトルケースに、残りを小文字にする |
| `title()` | O(n) | O(n) | 各単語をタイトルケースにする |
| `swapcase()` | O(n) | O(n) | |
| `casefold()` | O(n) | O(n) | 大文字・小文字を区別しない照合用 |
| **除去** ||||
| `strip(chars)` | O(n + (d+1)·c) | O(n) | d は除去する文字数で、各文字を `chars` の中から探す。何も除去しなければ `s` 自身を返す |
| `lstrip(chars)` | O(n + (d+1)·c) | O(n) | `strip()` と同じく、左側から |
| `rstrip(chars)` | O(n + (d+1)·c) | O(n) | `strip()` と同じく、右側から |
| **詰め物・寄せ** ||||
| `center(width)` | O(w) | O(w) | w ≤ n なら `s` 自身を返す |
| `ljust(width)` | O(w) | O(w) | w ≤ n なら `s` 自身を返す |
| `rjust(width)` | O(w) | O(w) | w ≤ n なら `s` 自身を返す |
| `zfill(width)` | O(w) | O(w) | w ≤ n なら `s` 自身を返す |
| **判定** ||||
| `isalnum()` | O(n) | O(1) | |
| `isalpha()` | O(n) | O(1) | |
| `isascii()` | O(1) | O(1) | `str` が保持するフラグを読む |
| `isdecimal()` | O(n) | O(1) | |
| `isdigit()` | O(n) | O(1) | |
| `isidentifier()` | O(n) | O(1) | |
| `islower()` | O(n) | O(1) | |
| `isnumeric()` | O(n) | O(1) | |
| `isprintable()` | O(n) | O(1) | |
| `isspace()` | O(n) | O(1) | |
| `istitle()` | O(n) | O(1) | |
| `isupper()` | O(n) | O(1) | |
| **書式化** ||||
| `format(*args, **kwargs)` | O(n) + 各フィールドの `format()` | O(n) + 各フィールドの `format()` | n はテンプレートの長さ。[format()](format.md) を参照 |
| `format_map(mapping)` | O(n) + 各フィールドの `format()` | O(n) + 各フィールドの `format()` | マッピングを使う `format()` |
| `s % values` | O(n) + 各変換 | O(n) + 各変換 | `%s` は `str()` を呼ぶ。[format()](format.md) を参照 |
| **エンコード** ||||
| `encode(encoding)` | O(n) | O(n) | バイト列に変換する。1 文字あたり一定量の処理をするコーデックを仮定する |

## コピーは同じ文字列を返す

厳密な `str` の文字列のコピーが元の文字列と異なることはありえないので、`s[:]`、`str(s)`、`copy.copy(s)` は O(1) で `s` 自身を返します。いくつかのメソッドも、変えるものがないときは同じように振る舞います。文字列より大きくない幅への詰め物、何も一致しないときの除去、`old` が現れないときの `replace()`、文字列 1 つだけの `join()` です。サブクラスのインスタンスは O(n) でコピーされます。

```python
import copy

s = "x" * 1_000_000
assert s[:] is s  # O(1)
assert str(s) is s  # O(1)
assert copy.copy(s) is s  # O(1)

assert s.center(10) is s  # w <= n
assert s.strip() is s  # nothing to strip
assert s.replace("y", "z") is s  # "y" does not occur
assert "".join([s]) is s  # a single piece


class Text(str):
    pass


t = Text("abc")
assert str(t) is not t and type(str(t)) is str  # O(n): a subclass is copied
```

## 文字の幅

各文字列は、最も幅の広い文字が必要とする幅で格納されます。U+00FF までは 1 文字あたり 1 バイト、U+FFFF までは 2 バイト、それを超えると 4 バイトです。幅の広い文字が 1 つあるだけで文字列全体の幅が広くなるため、より狭い部分文字列は探索の前に拡幅しなければなりません。

```python
import sys


def bytes_per_char(ch):
    return (sys.getsizeof(ch * 2_000) - sys.getsizeof(ch * 1_000)) // 1_000


assert bytes_per_char("a") == 1
assert bytes_per_char("é") == 1
assert bytes_per_char("世") == 2
assert bytes_per_char("😀") == 4

# One CJK character makes all 1,000 ASCII characters take 2 bytes each
assert sys.getsizeof("世" + "a" * 1_000) - sys.getsizeof("世") == 2_000
```

## 文字列の組み立て

空でない 2 つの文字列の `+` は新しい文字列を作るため、`+=` のループは各ステップでそれまでに組み立てたものをすべてコピーすることがあり、合計の長さに対して O(r²) になります。CPython は代わりに文字列をその場で伸ばせることもありますが、それはほかに何もその文字列を参照していない間だけです。途中の結果への参照がほかに 1 つでもあると、各ステップでコピーが発生します。`join()` は結果の大きさを一度で決め、各断片を一度ずつコピーします。

```python
pieces = [str(i) for i in range(10_000)]

joined = "".join(pieces)  # O(r + p)

built = ""
for piece in pieces:
    built += piece  # O(r²) at worst

assert built == joined
```

## 部分文字列の探索

前方探索（`in`、`find()`、`index()`、`count()`、および `split()`、`partition()`、`replace()` 内の探索）は最悪の場合でも線形です。後方探索（`rfind()`、`rindex()`、`rsplit()`、`rpartition()`）は典型的な入力では O(n) ですが、最悪の場合は O(n·m) です。`start` と `end` を渡すとその範囲だけが読まれ、先にスライスする場合と違って何もコピーされません。

```python
s = "a" * 1_000_000 + "b"

assert s.find("b") == 1_000_000  # O(n)
assert s.find("b", 0, 1_000) == -1  # O(1,000): only the region is read
assert "a" * 999 + "b" in s  # O(n), however long the pattern
assert s.rfind("ba") == -1  # O(n) here, O(n·m) at worst
```

## パフォーマンスのベストプラクティス

✅ **推奨**:

- 多数の断片から文字列を組み立てるには `"".join(pieces)` を使う。O(r + p) で一度だけ
- 先にスライスする代わりに、`find()` や `count()` に `start` と `end` を渡す。範囲はその場で読まれるが、スライスは O(j-i) 文字をコピーする
- 長いパターンでは後方探索より前方探索を選ぶ。最悪の場合 O(n) 対 O(n·m)

❌ **避けるべき**:

- 多数の断片に対するループ内での `+=`。途中の文字列への参照がほかにある場合は特に
- `strip()` に長い `chars` 引数を渡すこと。除去する文字ごとに `chars` の中を探す

## 関連する型

- **[Bytes](bytes.md)** - 不変なバイト列
- **[Bytearray](bytearray.md)** - 可変なバイト列
- **[str()](str_func.md)** - オブジェクトを文字列に変換する
- **[format()](format.md)** - f 文字列、`str.format()`、`%` による書式化
- **[正規表現 (re)](../stdlib/re.md)** - パターンマッチング

## さらに読む

- [CPython Internals: str](https://zpoint.github.io/CPython-Internals/BasicObject/str/str.html){ target="_blank" rel="noopener" }:material-open-in-new: -
  CPython の文字列実装を掘り下げた解説
