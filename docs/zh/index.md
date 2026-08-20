---
source_sha: de7f362c3fabad731fee5435a0f471b69a9972c08291bbdc9654ba4535d9242f
translated: machine
---

# Python 大 O 表示法：时间与空间复杂度参考

欢迎阅读这份关于 Python 操作复杂度的完整指南。本资料记录了 Python 内置操作和标准库函数的时间与空间复杂度，以及它们在不同 Python 版本和实现中的行为差异。

## 适合谁阅读

本参考面向希望写出高效代码、并在数据结构与算法之间做出合理选择的 **Python 开发者**。对于学习算法与数据结构的**计算机专业学生**，以及**准备技术面试**（复杂度分析是常见考点）的工程师，它同样很有价值。

这**不是** Python 教程，也不是
[Big-O](https://en.wikipedia.org/wiki/Big_O_notation){ target="_blank" rel="noopener" aria-label="访问大 O 表示法的维基百科条目" }
:material-open-in-new:
表示法的入门介绍。我们假定你已经熟悉 Python 基础，并对时间与空间复杂度的概念有大致了解。

## 快速开始

- **[内置类型](builtins/index.md)** - 列表、字典、集合、字符串和元组的复杂度分析
- **[标准库](stdlib/index.md)** - collections、heapq、bisect 等模块
- **[实现](implementations/index.md)** - CPython、PyPy、Jython 及其他实现的细节
- **[版本](versions/index.md)** - 各 Python 版本的变化与优化

## 为什么这很重要

理解复杂度可以帮助你：

- 写出高性能的 Python 代码
- 为你的场景选择合适的数据结构
- 预判代码在更大输入下的扩展性
- 有效地优化算法

## 示例：列表操作

列表操作的复杂度各不相同：

| 操作 | 时间复杂度 | 空间 |
|-----------|-----------------|-------|
| `append()` | 均摊 O(1) | - |
| `insert(0, x)` | O(n) | - |
| `pop()` | O(1) | - |
| `pop(0)` | O(n) | - |
| `in`（查找） | O(n) | - |
| `sort()` | O(n log n) | O(n) |

详细分析参见[内置类型](builtins/list.md)。

## 如何使用本指南

1. **搜索** - 使用搜索栏查找特定操作
2. **浏览** - 按类型或模块导航
3. **筛选** - 选择 Python 版本或实现
4. **查看备注** - 阅读与具体实现相关的注意事项

## 覆盖范围

- **Python 版本**：3.10-3.14
- **实现**：CPython、PyPy、Jython、IronPython
- **操作**：2200 多项内置与标准库操作
- **更新**：随 Python 新版本发布定期更新

## 为什么可以信任本文档？

本文档由多个 AI 编码代理（Amp、Claude、Gemini CLI、Kiro、Copilot、Codex）和模型（Opus 4.5+、Sonnet 4.5、Gemini 3 Pro、gpt-5.2+ 等）与人类贡献者共同审阅和完善。每个代理带来不同的视角、发现不同的问题，从而形成充分的交叉验证。不断扩充的单元测试套件会对照 Python 的实际行为验证这些复杂度结论。

本项目还**完全开源**——任何人都可以审阅内容、[提交问题](https://github.com/heikkitoivonen/python-time-space-complexity/issues)或[提出改进](https://github.com/heikkitoivonen/python-time-space-complexity/pulls)。所有来源均已注明，结论基于 Python 官方文档和 CPython 源代码。

## 参与贡献

发现错误或想补充内容？请查看我们的[贡献指南](https://github.com/heikkitoivonen/python-time-space-complexity/blob/main/CONTRIBUTING.md)。

## 参考来源

- [Python 官方文档](https://docs.python.org/3/)
- [TimeComplexity 维基页面](https://wiki.python.org/moin/TimeComplexity)
- [CPython 源代码](https://github.com/python/cpython)及实现细节
- [性能测试](https://github.com/heikkitoivonen/python-time-space-complexity/tree/main/tests)与基准测试

---

**免责声明**：尽管我们力求准确，复杂度特性仍可能因具体场景、输入规模和实现细节而不同。对性能关键的代码，请始终通过基准测试验证。
