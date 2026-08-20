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

| English            | Chinese      | Notes                                  |
|--------------------|--------------|----------------------------------------|
| time complexity    | 时间复杂度   |                                        |
| space complexity   | 空间复杂度   |                                        |
| Big-O notation     | 大 O 表示法  | space around the Latin `O`             |
| amortized          | 均摊         | alternative: 摊还                      |
| worst case         | 最坏情况     |                                        |
| average case       | 平均情况     |                                        |
| best case          | 最好情况     |                                        |
| operation          | 操作         |                                        |
| element / item     | 元素         |                                        |
| index              | 索引         |                                        |
| lookup             | 查找         |                                        |
| insertion          | 插入         |                                        |
| deletion / removal | 删除 / 移除  |                                        |
| traversal          | 遍历         |                                        |
| iteration          | 迭代         |                                        |
| slice              | 切片         |                                        |
| in place           | 原地         |                                        |
| overhead           | 开销         |                                        |
| trade-off          | 权衡         |                                        |

### Data structures

| English         | Chinese    | Notes                                     |
|-----------------|------------|-------------------------------------------|
| list            | 列表       |                                           |
| dictionary      | 字典       | the type is still written `dict`          |
| set             | 集合       |                                           |
| tuple           | 元组       |                                           |
| string          | 字符串     |                                           |
| bytes           | 字节       |                                           |
| array           | 数组       |                                           |
| hash table      | 哈希表     | also seen: 散列表                         |
| hash            | 哈希       | hash value: 哈希值                        |
| hash collision  | 哈希冲突   |                                           |
| linked list     | 链表       |                                           |
| heap            | 堆         |                                           |
| binary heap     | 二叉堆     |                                           |
| queue           | 队列       |                                           |
| deque           | 双端队列   | usually left as `deque` in running text   |
| stack           | 栈         |                                           |
| tree            | 树         |                                           |
| key / value     | 键 / 值    |                                           |

### Implementation vocabulary

| English            | Chinese    | Notes                          |
|--------------------|------------|--------------------------------|
| contiguous         | 连续       |                                |
| reference counting | 引用计数   |                                |
| garbage collection | 垃圾回收   |                                |
| memory allocation  | 内存分配   |                                |
| resizing           | 扩容       | shrinking: 缩容                |
| immutable          | 不可变     |                                |
| mutable            | 可变       |                                |
| interned           | 驻留       | of strings                     |
| built-in           | 内置       |                                |
| standard library   | 标准库     |                                |
| implementation     | 实现       |                                |
| benchmark          | 基准测试   |                                |
| sorting            | 排序       |                                |
| comparison         | 比较       |                                |
| binary search      | 二分查找   |                                |

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

## Adding a new locale

1. Add the locale to the `i18n` plugin's `languages` list in `mkdocs.yml`,
   with `site_name`, `site_description`, and `nav_translations`.
2. Confirm the locale has a lunr stemmer (`lunr.<locale>.js`) so search works;
   the plugin wires it up automatically when one exists.
3. Create `docs/<locale>/` and translate `index.md` first.
4. Add the locale to `LOCALES` in `scripts/validate_translations.py`.
