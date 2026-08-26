<!-- source_sha: 6bfbd6d7d30588319dd655b3a4818b2b4d618e0d0d7a90cc46395f6a97e940ca -->
<!-- translated: machine -->

[English](TRANSLATING.md) | **简体中文**

# 翻译指南

本项目从 `docs/` 下的语言子目录提供本地化文档。英文是默认语言，位于 `docs/` 根目录；每个翻译位于 `docs/<locale>/`，镜像英文目录树。

```
docs/builtins/list.md        -> https://pythoncomplexity.com/builtins/list/
docs/fi/builtins/list.md     -> https://pythoncomplexity.com/fi/builtins/list/
```

没有翻译的页面会自动回退到英文，因此部分翻译始终可以安全发布。

## 状态

| 区域 | 名称 | 阶段 |
|--------|----------|----------------------------|
| `en`   | English  | 完整(唯一权威来源) |
| `fi`   | Suomi    | 试点 - 14 页           |
| `zh`   | 简体中文 | 试点 - 14 页           |
| `ja`   | 日本語   | 试点 - 13 页           |

## 工作流程

1. 将英文页面复制到 `docs/<locale>/<相同路径>`。
2. 添加翻译 front matter(见下文)。
3. 翻译正文、标题、提示块标题和表格的 **备注** 列。
4. 保持代码块、标识符和复杂度表达式不变。
5. 运行 `make check` —— `scripts/validate_translations.py` 强制校验结构规则，并标记过期的翻译。
6. 用 `make serve-one LOCALE=<locale>` 预览，它会完全按照发布时的形态构建你的语言区域。`make serve-en` 不会渲染你的任何成果，而 `make serve` 会让所有语言共享同一个搜索索引。

## Front matter

每个翻译页面都带有其所依据英文源的 SHA-256:

```yaml
---
source_sha: 3f8a1c...
translated: machine
---
```

- `source_sha` — 翻译时英文文件字节的 SHA-256。当英文页面发生变化时，哈希不再匹配，验证器会将翻译标记为过期。
- `translated` — `machine`(未经审核)或 `reviewed`(由流利母语者检查过)。这是给维护者的簿记信息，不会显示在网站上；验证器只检查其是否为这两个值之一。

同一条命令既能为全新的翻译记录哈希，也能在你对照更新后的英文源重新检查页面后为它重新授权:

```bash
uv run python scripts/validate_translations.py --update-hashes fi
```

写完新页面后运行一次即可 - 你不需要手工计算哈希，上面的 front matter 块甚至可以完全不带 `source_sha` 行。在你运行它之前，验证器会说哈希*尚未记录*，这与它标记为 **STALE**(过期)是两回事:过期意味着英文源在一份已授权的翻译之下发生了变动，那种情况确实需要先重新阅读，再重新授权。

## 根目录文档

`README.md`、`CONTRIBUTING.md` 和 `TRANSLATING.md` 就地翻译为 `<stem>.<tag>.md`（如 `README.zh-CN.md`），使用完整的语言标签而不是裸语言区域代码，因为这是 GitHub 读者所期待的形式。每个文件都以一个链接到其兄弟文件的语言切换器开头，而这第一行是唯一允许与英文源不同的行。

它们不能携带 YAML front matter，因为 GitHub 会把它渲染成表格，所以它们的元数据改为放在文件顶部的 HTML 注释中：

```markdown
<!-- source_sha: 26ab06b2234ef5af328ca310db336739cfcd9de23fad475459c794b9a4449591 -->
<!-- translated: machine -->
```

这些键的含义与页面 front matter 中相同，`--update-hashes` 以同样的方式维护它们，结构规则也同样适用。若要扩大检查范围，请在 `scripts/validate_translations.py` 中向 `ROOT_DOC_STEMS` 添加文件名，或向 `ROOT_DOC_TAGS` 添加语言区域。

## 不要翻译的内容

| 原样保留 | 原因 |
|------------------------------------------|---------------------------------------------|
| 围栏代码块 | 代码就是代码 |
| `O(1)`, `O(n log n)`, `Θ`, `Ω` | 记法是语言无关的 |
| 方法和类型名(`append`, `dict`) | 它们是 Python 标识符，不是单词 |
| 模块名(`collections`, `heapq`) | 同上 |
| URL 和链接目标 | 路径是相对于语言区域解析的 |
| 表格结构(行数和列数) | 验证器会将其与英文对比 |

标题**会被**翻译，这会改变锚点 slug。因此跨页面链接必须指向文件(`builtins/list.md`)，绝不能指向其他页面中手写的锚点。

## 芬兰语词汇表(`fi`)

页面之间的一致性比任何单个词的选择都重要。修正此处任何读起来不对的地方，整个翻译就会随之受益。

### 核心术语

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

### 数据结构

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

### 实现词汇

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

### 提示块标题

| English   | Finnish   |
|-----------|-----------|
| Note      | Huomio    |
| Warning   | Varoitus  |
| Tip       | Vinkki    |
| Example   | Esimerkki |
| Important | Tärkeää   |

## 中文词汇表(`zh`)

简体中文。复杂度表达式保持拉丁字母形式(`O(n log n)`),Python 标识符从不翻译。

### 核心术语

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

### 数据结构

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

### 实现词汇

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

### 提示块标题

| English   | Chinese |
|-----------|---------|
| Note      | 注意    |
| Warning   | 警告    |
| Tip       | 提示    |
| Example   | 示例    |
| Important | 重要    |

### 搜索

中文没有词边界，因此搜索索引需要分词。Material 使用 `jieba` 实现这一点，这正是它作为项目依赖的原因。如果未安装，整个中文句子会变成一个搜索词元，搜索将基本失效。

jieba 会用零宽空格(`U+200B`)标记它找到的边界。`mkdocs.yml` 中搜索的 `separator` 列出了 `\u200b`，以便浏览器按其切分 - JavaScript 的 `\s` **不**匹配 `U+200B`，若不列出，零宽空格会被当作词的一部分一起索引，分词也就白做了。

只要 jieba 可以导入，Material 就会无条件启用它，判据是汉字*书写系统*，这意味着它在日语汉字上同样会触发。因此 `scripts/mkdocs_hooks.py` 只在构建 `zh` 语言区域时才启用它。至于这为什么重要，请参阅下方的日语搜索说明。

## 日语词汇表(`ja`)

正文使用敬体(です・ます体)撰写。复杂度表达式保持拉丁文字(`O(n log n)`)，Python 标识符绝不翻译。

### 核心术语

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

### 数据结构

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

### 实现词汇

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

### 提示块标题

| English   | Japanese |
|-----------|----------|
| Note      | 注意     |
| Warning   | 警告     |
| Tip       | ヒント   |
| Example   | 例       |
| Important | 重要     |

### 搜索

日语同样需要分词，但不来自 Python：Material 自带 `lunr.ja.js` 和 TinySegmenter，只要 `ja` 出现在搜索的 `lang` 列表中，两者都会在浏览器中加载。无需额外依赖。

日语真正需要的是**不受** jieba 影响。jieba 的词典是简体中文的，因此在日语文本上会切分并非中文词的汉字复合词 - `組み込み` 曾被索引为 組/み/込/み，`実装` 被索引为 実/装，搜索二者都返回空结果。在 13 个日语页面上实测，41 个代表性查询在启用 jieba 时解析出 28 次，禁用后为 40 次。`scripts/mkdocs_hooks.py` 正是出于这个原因把 jieba 限定在 `zh` 上；如果你添加第三个 CJK 语言区域，请慎重决定它应归于该钩子的哪一侧。


## 添加新语言区域

1. 在 `mkdocs.yml` 中将该语言添加到 `i18n` 插件的 `languages` 列表，包括 `site_name`、`site_description` 和 `nav_translations`。
2. 确认该语言有 lunr 词干分析器(`lunr.<locale>.js`)以便搜索可用；存在时插件会自动接入。没有词边界的语言还需要分词器 - 请参阅上面的中文和日语搜索说明，并检查该语言区域是否应归入 `scripts/mkdocs_hooks.py` 中的 `SEGMENTED_LOCALES`。
3. 在 `docs/overrides/main.html` 的 `fallback_notices` 中添加该语言的字符串，并在同一文件中翻译公告栏。没有条目的语言区域只不显示提示。
4. 翻译 `docs/overrides/partials/copyright.html` 中的页脚署名。没有条目的语言区域会回退到英文。
5. 创建 `docs/<locale>/` 并首先翻译 `index.md`。
6. 在 `scripts/validate_translations.py` 中将该语言添加到 `LOCALES`。
7. 在上面的状态表和 `CONTRIBUTING.md` 的状态表中各添加一行。

## 每个语言区域一个站点

生产环境不会把各语言区域构建到同一棵树中。`scripts/build_site.py` 借助 i18n 插件的
`build_only_locale` 分别构建每一个语言区域，因此每个语言区域都得到一个完整的独立站点：有翻译的地方用翻译页面，其余一律回退到英文，并且**拥有自己的搜索索引**。默认语言区域位于站点根目录，其余位于各自的子目录中 - 两种方式下的 URL 布局是一致的。

这样做是为了搜索。模块名和方法名在每个翻译中都保持原样 - 这正是 `collections.md#deque` 能够解析的原因 - 因此在共享索引中，一次英文的 `bisect` 或 `deque` 搜索也会匹配到芬兰语、中文和日语页面，而且是在*标题*中匹配，而 Material 会给标题 1000 倍的权重。在一组典型的英文查询中，21-74% 的匹配结果是外语页面。改用按语言区域独立的索引后，这一比例为 0%。

当 i18n 插件只构建一种语言时，有四件事会出错或被跳过，`scripts/mkdocs_hooks.py` 会把它们补回来：

- **规范 URL。** 语言区域在自己那棵树的根目录构建，却从子目录提供服务，因此必须把语言区域前缀加回 `site_url`。
- **语言切换器。** 插件仅在构建多于一种语言时才生成 `extra.alternate`。该钩子会根据已配置的语言区域重建它，并让每个条目指向对应的页面，而不是另一语言区域的首页。
- **哪个文件胜出。** `build_only_locale` 会把正在构建的语言区域标记为默认语言区域，因此插件也会给英文源文件打上同样的标记，于是再也分不清翻译和回退。它的决胜规则就变成了「最后走到的文件」，而 `docs/` 是按字母顺序遍历的 - 因此只有当语言区域目录排在它所镜像的目录之后时，翻译才会被采用。`docs/zh/` 排在所有目录之后；而 `docs/fi/stdlib/` 和 `docs/ja/stdlib/` 输给了 `docs/stdlib/`，被悄无声息地从站点中丢弃。该钩子会把当前语言区域自己的文件排到最后，让决胜规则得出正确结果。
- **回退标记。** 出于同样的原因，页面的语言区域永远等于正在构建的语言区域，因此无法据此推导未翻译页面的提示。该钩子改为依据源文件路径设置 `i18n_is_fallback`。

添加语言区域无需改动此处：脚本会从 `mkdocs.yml` 读取语言区域列表。

## 页脚

页脚中有两个字符串是我们自己的，而不是 Material 的。

署名位于 `docs/overrides/partials/copyright.html`。产品名前后的语序因语言而异，因此每个语言区域都承载整个短语并在其中插入链接，而不是把 "Made with" 当作片段来翻译。`Material for MkDocs` 是专有名词，保持不译。

版权声明是 `mkdocs.yml` 中的 `copyright:`，并且刻意**不**按语言区域区分。它只有符号和年份，前面不带任何词：该符号是国际通用标记，没有本地化变体，本身即可传达含义，因此一个字符串在每个语言区域都读得通，而且只有一处需要更新年份。`mkdocs-static-i18n` 确实支持按语言区域设置 `copyright`，所以这是一个选择，而不是限制 - 只有当某个语言区域确实需要不同措辞时才重新考虑。注意该值必须在 `mkdocs.yml` 中加引号，因为开头的 `&` 是 YAML 锚点语法。

页脚上其余的内容 - 仓库提示框、启用 `navigation.footer` 时的上一页/下一页标签 - 都来自 Material 自己的翻译，会跟随主题语言，无需我们做任何工作。

## 未翻译页面的提示

没有翻译的页面会在本地化 URL 下以英文源提供。如果没有提示，这看起来像一个 bug：读者要求的是中文，得到的却是英文。

因此 `docs/overrides/main.html` 会在当前语言区域尚无翻译的任何页面顶部显示一条简短提示。已翻译页面和英文页面不显示任何内容。

它依据 `i18n_is_fallback`，该值由 `scripts/mkdocs_hooks.py` 根据页面的源文件路径逐页设置，因此无需 front matter，也不会与实际内容失同步。不要把它换成与 `page.file.locale` 的比较：`build_only_locale` 会把正在构建的语言区域变成默认语言区域，因此按语言区域构建时每个文件都带有该语言区域，比较永远不成立 - 提示会从实际发布的构建中悄悄消失，而 `make serve` 里却仍然显示。
