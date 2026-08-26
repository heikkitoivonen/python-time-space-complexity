[English](TRANSLATING.md) | **简体中文**

# 翻译指南

本项目从 `docs/` 下的语言子目录提供本地化文档。英文是默认语言,位于 `docs/` 根目录;每个翻译位于 `docs/<locale>/`,镜像英文目录树。

```
docs/builtins/list.md        -> https://pythoncomplexity.com/builtins/list/
docs/fi/builtins/list.md     -> https://pythoncomplexity.com/fi/builtins/list/
```

没有翻译的页面会自动回退到英文,因此部分翻译始终可以安全发布。

## 状态

| 区域 | 名称 | 阶段 |
|--------|----------|----------------------------|
| `en`   | English  | 完整(唯一权威来源) |
| `fi`   | Suomi    | 试点 - 13 页           |
| `zh`   | 简体中文 | 试点 - 14 页           |

## 工作流程

1. 将英文页面复制到 `docs/<locale>/<相同路径>`。
2. 添加翻译 front matter(见下文)。
3. 翻译正文、标题、提示块标题和表格的 **备注** 列。
4. 保持代码块、标识符和复杂度表达式不变。
5. 运行 `make check` —— `scripts/validate_translations.py` 强制校验结构规则,并标记过期的翻译。

## Front matter

每个翻译页面都带有其所依据英文源的 SHA-256:

```yaml
---
source_sha: 3f8a1c...
translated: machine
---
```

- `source_sha` — 翻译时英文文件字节的 SHA-256。当英文页面发生变化时,哈希不再匹配,验证器会将翻译标记为过期。
- `translated` — `machine`(未经审核)或 `reviewed`(由流利母语者检查过)。这是给维护者的簿记信息,不会显示在网站上;验证器只检查其是否为这两个值之一。

在对照更新后的英文源重新检查页面后,重新授权(消除过期标记):

```bash
uv run python scripts/validate_translations.py --update-hashes fi
```

## 不要翻译的内容

| 原样保留 | 原因 |
|------------------------------------------|---------------------------------------------|
| 围栏代码块 | 代码就是代码 |
| `O(1)`, `O(n log n)`, `Θ`, `Ω` | 记法是语言无关的 |
| 方法和类型名(`append`, `dict`) | 它们是 Python 标识符,不是单词 |
| 模块名(`collections`, `heapq`) | 同上 |
| URL 和链接目标 | 路径是相对于语言区域解析的 |
| 表格结构(行数和列数) | 验证器会将其与英文对比 |

标题**会被**翻译,这会改变锚点 slug。因此跨页面链接必须指向文件(`builtins/list.md`),绝不能指向其他页面中手写的锚点。

## 芬兰语词汇表(`fi`)

页面之间的一致性比任何单个词的选择都重要。修正此处任何读起来不对的地方,整个翻译就会随之受益。

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

中文没有词边界,因此搜索索引需要分词。Material 使用 `jieba` 实现这一点,这正是它作为项目依赖的原因。如果未安装,整个中文句子会变成一个搜索词元,搜索将基本失效。

## 添加新语言区域

1. 在 `mkdocs.yml` 中将该语言添加到 `i18n` 插件的 `languages` 列表,包括 `site_name`、`site_description` 和 `nav_translations`。
2. 确认该语言有 lunr 词干分析器(`lunr.<locale>.js`)以便搜索可用;存在时插件会自动接入。没有词边界的语言还需要分词器 - 请参阅上面的中文说明。
3. 在 `docs/overrides/main.html` 的 `fallback_notices` 中添加该语言的字符串,并在同一文件中翻译公告栏。没有条目的语言区域只不显示提示。
4. 创建 `docs/<locale>/` 并首先翻译 `index.md`。
5. 在 `scripts/validate_translations.py` 中将该语言添加到 `LOCALES`。
6. 在上面的状态表和 `CONTRIBUTING.md` 的状态表中各添加一行。

## 未翻译页面的提示

没有翻译的页面会在本地化 URL 下以英文源提供。如果没有提示,这看起来像一个 bug:读者要求的是中文,得到的却是英文。

因此 `docs/overrides/main.html` 会在任何源语言与当前构建语言不同的页面顶部显示一条简短提示。它依据 `page.file.locale`,该值由 i18n 插件按文件设置,因此无需 front matter,也不会与实际内容失同步。已翻译页面和英文页面不显示任何内容。
