<!-- source_sha: 6f320435c5fdcc8dfc0d7fe9dffcd5535043df6597b8e875cd7c9f2ca486260b -->
<!-- translated: machine -->

[English](CONTRIBUTING.md) | **简体中文**

# 参与 Python Big-O：时间与空间复杂度

感谢你对本项目的关注与贡献！本指南将帮助你快速上手。

## 如何参与贡献

### 报告错误

发现复杂度分析有误？请提交 issue，并附上：
- 受影响的操作或模块
- 文档描述与正确内容之间的差异
- 来源或证据(Python 文档、实现、基准测试结果)

### 添加文档

帮助我们扩展以下内容的覆盖范围：
- 更多标准库模块(`itertools`、`functools`、`json` 等)
- 更多内置函数
- 实现特定的细节
- 版本特定的行为

### 改进现有内容

- 澄清解释
- 添加更多示例
- 修复拼写或格式错误
- 添加性能提示

### 翻译文档

通过翻译页面、修正现有翻译或添加新的语言来帮助其他语言的读者。请参阅下方的[国际化与本地化](#国际化与本地化)以及 [TRANSLATING.md](TRANSLATING.md) 中的完整指南。

## 流程

1. **Fork** 仓库
2. **创建分支**:`git checkout -b feature/what-you-add`
3. **修改代码**，遵循下方指南
4. **本地测试**:`mkdocs serve`
5. **提交 PR**，附上清晰描述

## 文档风格指南

### 文件结构

```
docs/
├── section/
│   ├── index.md      # Overview
│   └── item.md       # Details
```

### 复杂度表格格式

```markdown
| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `method()` | O(n) | O(1) | Brief description |
```

### 代码示例

```python
# Clear, runnable examples
def example():
    lst = [1, 2, 3]
    lst.append(4)  # O(1)
```

### 提示块

用于重要提示：

```markdown
!!! warning "Warning Title"
    Warning content

!!! tip "Tip Title"
    Tip content

!!! note "Note Title"
    Note content
```

## 内容指南

### 复杂度标准

- 始终包含时间复杂度
- 在相关时包含空间复杂度
- 注明均摊与最坏情况
- 标注 Python 版本差异

### 准确性要求

- 以官方 Python 文档为来源
- 尽可能用 CPython 实现验证
- 用实际基准测试验证结论
- 对不显而易见的复杂度引用来源

### 示例

- 展示真实用例
- 在有用时与替代方案对比
- 解释为何某些方案更受青睐
- 同时包含好的和坏的模式

## 国际化与本地化

英文是唯一权威来源。翻译文件位于镜像英文目录的语言子目录中，并在区域前缀下提供访问：

```
docs/builtins/list.md      ->  https://pythoncomplexity.com/builtins/list/
docs/fi/builtins/list.md   ->  https://pythoncomplexity.com/fi/builtins/list/
```

| 区域 | 语言 | 状态 |
|--------|----------|----------------------------|
| `en`   | English  | 完整(唯一权威来源) |
| `fi`   | Suomi    | 试点 - 13 页           |
| `zh`   | 简体中文 | 试点 - 14 页           |
| `ja`   | 日本語   | 试点 - 13 页           |

没有翻译的页面会自动回退到英文，因此部分翻译始终可以安全合并。你无需在贡献前翻译整个章节。这些回退页面会以读者语言显示一条简短提示，说明该页面尚未翻译，因此本地化 URL 下的英文内容不会被视为 bug。

### 基本原则

- **翻译正文、标题、提示块标题和备注列。** 其余内容保持英文原文。
- **切勿修改代码块。** 围栏内的标识符、注释和输出必须与英文源逐字节一致。
- **切勿更改复杂度记号。** `O(1)`、`O(n log n)` 等表示法是语言无关的。
- **保持表格结构。** 行数和列数必须与英文页面一致。
- **使用词汇表。** 页面之间的一致性比任何单个词的选择都重要。每个语言在 [TRANSLATING.md](TRANSLATING.md) 中都有一个词汇表；确定新术语时请扩展它。

### 检查

翻译会作为 `make check` 的一部分自动验证：

```bash
uv run python scripts/validate_translations.py
```

它会验证每个翻译页面都有对应的英文页面、代码块和表格结构仍然匹配、页面未过期。每个翻译都记录其所依据英文文件的 SHA-256，因此当英文页面更改时，其翻译会被标记，直到有人更新它们。

### 添加语言

欢迎添加新的语言，包括部分翻译。具体步骤(插件配置、搜索词干分析器、第一个页面、验证器注册)详见 [TRANSLATING.md](TRANSLATING.md)。

## 本地构建

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Serve English only - roughly 4x faster, and what you want for most work
make serve-en

# Serve one locale exactly as it ships, search index included
make serve-one LOCALE=ja

# Serve every locale in one tree (quick cross-locale browsing)
make serve

# Visit http://localhost:8000
# Translated pages live under a locale prefix, e.g. http://localhost:8000/fi/
```

每个语言区域都会构建成独立完整的站点，因此每增加一种语言，构建开销就大致再多一倍。`make serve-en` 和 `make build-en` 只构建英文，可以把一次完整构建从大约 40 秒缩短到 10 秒。撰写英文页面时可以放心使用它们。

提交前有两点需要注意：

- 仅英文的构建不会产生本地化页面，也不会产生未翻译页面的提示，因此它无法暴露这些内容中的任何问题。
- `make serve` 是唯一把所有语言区域放进同一棵树的模式。它便于在语言之间点击切换，但它的搜索索引是所有语言共享的，这*不是*站点实际发布的方式。请用 `make serve-one LOCALE=<locale>` 来检查搜索。

## 提交信息

使用清晰、描述性的信息：

```
Add: Complexity analysis for collections.deque

Fix: Incorrect complexity for string.replace()

Update: Python 3.12 performance notes

Docs: Improve list.insert() explanation
```

## PR 描述模板

```markdown
## What This Changes

Brief description of changes.

## Why

Explain the motivation.

## Type of Change

- [ ] New content
- [ ] Bug fix
- [ ] Documentation improvement
- [ ] Structure/organization

## Related Issues

Closes #(issue number) if applicable
```

## 评审流程

- 合并前至少需要一次评审
- 用来源验证准确性
- 检查与风格指南的一致性
- 测试本地构建是否正常

## 有问题？

提交 issue 提出你的问题。我们乐于提供帮助！

## 许可证

参与贡献即表示你同意你的工作以 MIT 许可证授权(与项目相同)。

## 行为准则

- 保持尊重与包容
- 提供建设性反馈
- 相信他人善意
- 向维护者报告违规行为

感谢你帮助让 Python 复杂度文档变得更好！
