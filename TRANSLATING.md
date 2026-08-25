**English** | [简体中文](TRANSLATING.zh-CN.md)

# Translating

This project serves localized documentation from language subdirectories under
`docs/`. English is the default language and lives at the repository root of
`docs/`; each translation lives in `docs/<locale>/` mirroring the English tree.

```
docs/builtins/list.md        -> https://pythoncomplexity.com/builtins/list/
docs/fi/builtins/list.md     -> https://pythoncomplexity.com/fi/builtins/list/
```

Pages without a translation fall back to English automatically, so a partial
translation is always safe to ship.

## Status

| Locale | Name     | Stage                      |
|--------|----------|----------------------------|
| `en`   | English  | Complete (source of truth) |
| `fi`   | Suomi    | Pilot - 13 pages           |
| `zh`   | 简体中文 | Pilot - 13 pages           |
| `ja`   | 日本語   | Pilot - 13 pages           |

## Workflow

1. Copy the English page to `docs/<locale>/<same path>`.
2. Add the translation front matter (see below).
3. Translate prose, headings, admonition titles, and table **Notes** cells.
4. Leave code blocks, identifiers, and complexity expressions untouched.
5. Run `make check` — `scripts/validate_translations.py` enforces the
   structural rules and flags stale translations.

## Front matter

Every translated page carries the SHA-256 of the English source it was made
from:

```yaml
---
source_sha: 3f8a1c...
translated: machine
---
```

- `source_sha` — SHA-256 of the English file's bytes at translation time. When
  the English page changes, the hash no longer matches and the validator
  reports the translation as stale.
- `translated` — `machine` (unreviewed) or `reviewed` (checked by a fluent
  speaker). This is bookkeeping for maintainers and is not surfaced on the
  site; the validator only checks that it is one of those two values.

To re-bless a page after re-checking it against an updated English source:

```bash
uv run python scripts/validate_translations.py --update-hashes fi
```

## What not to translate

| Keep verbatim                            | Why                                         |
|------------------------------------------|---------------------------------------------|
| Fenced code blocks                       | Code is code                                |
| `O(1)`, `O(n log n)`, `Θ`, `Ω`           | Notation is language-neutral                |
| Method and type names (`append`, `dict`) | They are Python identifiers, not words      |
| Module names (`collections`, `heapq`)    | Ditto                                       |
| URLs and link targets                    | Paths are resolved relative to the locale   |
| Table structure (row and column counts)  | The validator compares them against English |

Headings **are** translated, which changes anchor slugs. Cross-page links must
therefore point at files (`builtins/list.md`), never at hand-written anchors in
another page.

## Finnish glossary (`fi`)

Consistency across pages matters more than any individual word choice. Correct
anything here that reads wrong and the whole translation follows.

### Core terms

| English            | Finnish               | Notes                     |
|--------------------|-----------------------|---------------------------|
| time complexity    | aikavaativuus         |                           |
| space complexity   | tilavaativuus         |                           |
| Big-O notation     | O-notaatio            | also seen: iso-O-notaatio |
| amortized          | tasoitettu            | alternative: amortisoitu  |
| worst case         | pahin tapaus          |                           |
| average case       | keskimääräinen tapaus |                           |
| best case          | paras tapaus          |                           |
| operation          | operaatio             |                           |
| element / item     | alkio                 |                           |
| index              | indeksi               |                           |
| lookup             | haku                  |                           |
| insertion          | lisäys                |                           |
| deletion / removal | poisto                |                           |
| traversal          | läpikäynti            |                           |
| iteration          | iterointi             |                           |
| slice              | viipale               | verb: viipalointi         |
| in place           | paikallaan            |                           |
| overhead           | lisäkustannus         |                           |
| trade-off          | kompromissi           |                           |

### Data structures

| English        | Finnish          | Notes                                   |
|----------------|------------------|-----------------------------------------|
| list           | lista            |                                         |
| dictionary     | sanakirja        | the type is still written `dict`        |
| set            | joukko           |                                         |
| tuple          | monikko          |                                         |
| string         | merkkijono       |                                         |
| bytes          | tavut            |                                         |
| array          | taulukko         |                                         |
| hash table     | hajautustaulu    |                                         |
| hash           | tiiviste         | verb: hajauttaa                         |
| hash collision | tiivistetörmäys  |                                         |
| linked list    | linkitetty lista |                                         |
| heap           | keko             |                                         |
| binary heap    | binäärikeko      |                                         |
| queue          | jono             |                                         |
| deque          | pakka            | usually left as `deque` in running text |
| stack          | pino             |                                         |
| tree           | puu              |                                         |
| key / value    | avain / arvo     |                                         |

### Implementation vocabulary

| English            | Finnish              | Notes                          |
|--------------------|----------------------|--------------------------------|
| contiguous         | yhtenäinen           |                                |
| reference counting | viittausten laskenta |                                |
| garbage collection | roskienkeruu         |                                |
| memory allocation  | muistinvaraus        |                                |
| resizing           | koon muuttaminen     |                                |
| immutable          | muuttumaton          |                                |
| mutable            | muuttuva             |                                |
| interned           | sisäistetty          | of strings; often left English |
| built-in           | sisäänrakennettu     |                                |
| standard library   | standardikirjasto    |                                |
| implementation     | toteutus             |                                |
| benchmark          | suorituskykymittaus  | verb: mitata suorituskykyä     |
| sorting            | järjestäminen        | not "lajittelu" in CS contexts |
| comparison         | vertailu             |                                |
| binary search      | binäärihaku          |                                |

### Admonition titles

| English   | Finnish   |
|-----------|-----------|
| Note      | Huomio    |
| Warning   | Varoitus  |
| Tip       | Vinkki    |
| Example   | Esimerkki |
| Important | Tärkeää   |

## Chinese glossary (`zh`)

Simplified Chinese. Complexity expressions stay in Latin script (`O(n log n)`),
and Python identifiers are never translated.

### Core terms

| English            | Chinese     | Notes                      |
|--------------------|-------------|----------------------------|
| time complexity    | 时间复杂度  |                            |
| space complexity   | 空间复杂度  |                            |
| Big-O notation     | 大 O 表示法 | space around the Latin `O` |
| amortized          | 均摊        | alternative: 摊还          |
| worst case         | 最坏情况    |                            |
| average case       | 平均情况    |                            |
| best case          | 最好情况    |                            |
| operation          | 操作        |                            |
| element / item     | 元素        |                            |
| index              | 索引        |                            |
| lookup             | 查找        |                            |
| insertion          | 插入        |                            |
| deletion / removal | 删除 / 移除 |                            |
| traversal          | 遍历        |                            |
| iteration          | 迭代        |                            |
| slice              | 切片        |                            |
| in place           | 原地        |                            |
| overhead           | 开销        |                            |
| trade-off          | 权衡        |                            |

### Data structures

| English        | Chinese  | Notes                                   |
|----------------|----------|-----------------------------------------|
| list           | 列表     |                                         |
| dictionary     | 字典     | the type is still written `dict`        |
| set            | 集合     |                                         |
| tuple          | 元组     |                                         |
| string         | 字符串   |                                         |
| bytes          | 字节     |                                         |
| array          | 数组     |                                         |
| hash table     | 哈希表   | also seen: 散列表                       |
| hash           | 哈希     | hash value: 哈希值                      |
| hash collision | 哈希冲突 |                                         |
| linked list    | 链表     |                                         |
| heap           | 堆       |                                         |
| binary heap    | 二叉堆   |                                         |
| queue          | 队列     |                                         |
| deque          | 双端队列 | usually left as `deque` in running text |
| stack          | 栈       |                                         |
| tree           | 树       |                                         |
| key / value    | 键 / 值  |                                         |

### Implementation vocabulary

| English            | Chinese  | Notes           |
|--------------------|----------|-----------------|
| contiguous         | 连续     |                 |
| reference counting | 引用计数 |                 |
| garbage collection | 垃圾回收 |                 |
| memory allocation  | 内存分配 |                 |
| resizing           | 扩容     | shrinking: 缩容 |
| immutable          | 不可变   |                 |
| mutable            | 可变     |                 |
| interned           | 驻留     | of strings      |
| built-in           | 内置     |                 |
| standard library   | 标准库   |                 |
| implementation     | 实现     |                 |
| benchmark          | 基准测试 |                 |
| sorting            | 排序     |                 |
| comparison         | 比较     |                 |
| binary search      | 二分查找 |                 |

### Admonition titles

| English   | Chinese |
|-----------|---------|
| Note      | 注意    |
| Warning   | 警告    |
| Tip       | 提示    |
| Example   | 示例    |
| Important | 重要    |

### Search

Chinese has no word boundaries, so the search index needs segmentation.
Material does this with `jieba`, which is a project dependency for exactly this
reason. Without it installed, an entire Chinese sentence becomes a single
search token and search effectively stops working.

jieba marks the boundaries it finds with zero-width spaces (`U+200B`). The
search `separator` in `mkdocs.yml` lists `\u200b` so the browser splits on
them - JavaScript's `\s` does **not** match `U+200B`, so without it the
zero-width spaces are indexed as part of the words and the segmentation is
wasted.

Material applies jieba unconditionally whenever it is importable, keyed on the
Han *script*, which means it also fires on Japanese kanji. `scripts/mkdocs_hooks.py`
therefore enables it only while the `zh` locale is being built. See the
Japanese search note below for why that matters.

## Japanese glossary (`ja`)

Prose is written in polite form (です・ます体). Complexity expressions stay in
Latin script (`O(n log n)`), and Python identifiers are never translated.

### Core terms

| English            | Japanese       | Notes                        |
|--------------------|----------------|------------------------------|
| time complexity    | 時間計算量     |                              |
| space complexity   | 空間計算量     |                              |
| Big-O notation     | O 記法         | space around the Latin `O`   |
| amortized          | 償却           |                              |
| worst case         | 最悪の場合     |                              |
| average case       | 平均の場合     |                              |
| best case          | 最良の場合     |                              |
| operation          | 操作           |                              |
| element / item     | 要素           |                              |
| index              | 添字           | インデックス is also fine    |
| lookup             | 探索           |                              |
| insertion          | 挿入           |                              |
| deletion / removal | 削除           |                              |
| traversal          | 走査           |                              |
| iteration          | 反復           |                              |
| slice              | スライス       |                              |
| in place           | その場で       |                              |
| overhead           | オーバーヘッド |                              |
| trade-off          | トレードオフ   |                              |

### Data structures

| English        | Japanese         | Notes                                   |
|----------------|------------------|-----------------------------------------|
| list           | リスト           |                                         |
| dictionary     | 辞書             | the type is still written `dict`        |
| set            | 集合             |                                         |
| tuple          | タプル           |                                         |
| string         | 文字列           |                                         |
| bytes          | バイト列         |                                         |
| array          | 配列             |                                         |
| hash table     | ハッシュテーブル |                                         |
| hash           | ハッシュ         |                                         |
| hash collision | ハッシュ衝突     |                                         |
| linked list    | 連結リスト       |                                         |
| heap           | ヒープ           |                                         |
| binary heap    | 二分ヒープ       |                                         |
| queue          | キュー           |                                         |
| deque          | 両端キュー       | usually left as `deque` in running text |
| stack          | スタック         |                                         |
| tree           | 木               |                                         |
| key / value    | キー / 値        |                                         |

### Implementation vocabulary

| English            | Japanese             | Notes                     |
|--------------------|----------------------|---------------------------|
| contiguous         | 連続した             |                           |
| reference counting | 参照カウント         |                           |
| garbage collection | ガベージコレクション |                           |
| memory allocation  | メモリ確保           |                           |
| resizing           | リサイズ             |                           |
| immutable          | 不変                 |                           |
| mutable            | 可変                 |                           |
| interned           | インターン           | of strings                |
| built-in           | 組み込み             |                           |
| standard library   | 標準ライブラリ       |                           |
| implementation     | 実装                 |                           |
| benchmark          | ベンチマーク         |                           |
| sorting            | ソート               | 整列 in formal CS writing |
| comparison         | 比較                 |                           |
| binary search      | 二分探索             |                           |

### Admonition titles

| English   | Japanese |
|-----------|----------|
| Note      | 注意     |
| Warning   | 警告     |
| Tip       | ヒント   |
| Example   | 例       |
| Important | 重要     |

### Search

Japanese needs segmentation too, but not from Python: Material ships
`lunr.ja.js` and TinySegmenter and loads both in the browser whenever `ja` is
in the search `lang` list. No extra dependency is required.

What Japanese does need is protection *from* jieba. jieba's dictionary is
Simplified Chinese, so on Japanese text it splits kanji compounds that are not
Chinese words - `組み込み` was indexed as 組/み/込/み and `実装` as 実/装, and
searching for either returned nothing. Measured over the 13 Japanese pages, 41
representative queries resolved 28 times with jieba and 40 times without it.
`scripts/mkdocs_hooks.py` keeps jieba scoped to `zh` for that reason; if you
add a third CJK locale, decide deliberately which side of that hook it belongs
on.

## Adding a new locale

1. Add the locale to the `i18n` plugin's `languages` list in `mkdocs.yml`,
   with `site_name`, `site_description`, and `nav_translations`.
2. Confirm the locale has a lunr stemmer (`lunr.<locale>.js`) so search works;
   the plugin wires it up automatically when one exists. Languages without
   word boundaries need a segmenter too - see the Chinese and Japanese search
   notes above, and check whether the locale belongs in `SEGMENTED_LOCALES` in
   `scripts/mkdocs_hooks.py`.
3. Add the locale's strings to `fallback_notices` in
   `docs/overrides/main.html`, and translate the announce bar in the same
   file. A locale with no entry simply shows no notice.
4. Translate the footer attribution in
   `docs/overrides/partials/copyright.html`. A locale with no entry falls
   back to English.
5. Create `docs/<locale>/` and translate `index.md` first.
6. Add the locale to `LOCALES` in `scripts/validate_translations.py`.
7. Add a row to the status table above and to the one in `CONTRIBUTING.md`.

## The footer

Two strings in the footer are ours rather than Material's.

The attribution lives in `docs/overrides/partials/copyright.html`. Word order
around the product name differs by language, so each locale carries the whole
phrase and interpolates the link, instead of translating "Made with" as a
fragment. `Material for MkDocs` is a proper noun and stays untranslated.

The copyright notice is `copyright:` in `mkdocs.yml` and is deliberately
**not** per-locale. It is the symbol and the year, with no word in front: the
symbol is an international mark with no localized variant and carries the
meaning on its own, so one string reads correctly in every locale and there is
only one place to bump the year. `mkdocs-static-i18n` does support a per-locale
`copyright`, so this is a choice, not a limitation - revisit it only if a
locale genuinely needs different wording. Note the value has to be quoted in
`mkdocs.yml`, because a leading `&` is YAML anchor syntax.

Everything else down there - the repository tooltip, the previous/next labels
when `navigation.footer` is enabled - comes from Material's own translations
and follows the theme language with no work from us.

## The untranslated-page notice

Pages that have no translation are served from the English source under the
localized URL. Without a hint, that reads as a bug: the reader asked for
Chinese and got English.

`docs/overrides/main.html` therefore shows a short notice at the top of any
page whose source locale differs from the locale being built. It keys off
`page.file.locale`, which the i18n plugin sets per file, so it needs no front
matter and cannot fall out of sync with the actual content. Translated pages
and English pages show nothing.
