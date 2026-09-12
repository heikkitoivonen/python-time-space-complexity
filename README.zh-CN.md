<!-- source_sha: a7a8a9a77a5a4e8b96f4d49647a1722bfcf72f75b21f985ceae3c723869ff076 -->
<!-- translated: machine -->

[English](README.md) | **简体中文**

# Python Big-O：时间复杂度与空间复杂度

[![Lint / Format](https://img.shields.io/github/actions/workflow/status/heikkitoivonen/python-time-space-complexity/deploy.yml?label=lint%20%2F%20format)](https://github.com/heikkitoivonen/python-time-space-complexity/actions/workflows/deploy.yml)
[![Type Check](https://img.shields.io/github/actions/workflow/status/heikkitoivonen/python-time-space-complexity/deploy.yml?label=type%20check)](https://github.com/heikkitoivonen/python-time-space-complexity/actions/workflows/deploy.yml)
[![Python](https://img.shields.io/badge/python-3.10%20to%203.14-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/heikkitoivonen/python-time-space-complexity)](LICENSE.txt)
[![Docs](https://img.shields.io/badge/docs-pythoncomplexity.com-brightgreen)](https://pythoncomplexity.com)

一个全面记录 Python 内置函数和标准库操作在不同 Python 版本和实现中的时间与空间复杂度的资源。

## 概述

本项目提供以下内容的详细算法复杂度文档：
- **Python 内置类型**：`list`、`dict`、`set`、`str` 等
- **标准库模块**：`collections`、`heapq`、`bisect`、`annotationlib`、`compression.zstd` 等
- **Python 版本**：3.10–3.14（包含新的 3.14 特性）
- **替代实现**：CPython、PyPy、Jython、IronPython

## 特性

- 📊 覆盖所有主要内置类型和操作的全面复杂度表
- 🔄 版本特定的行为和优化变更
- 🚀 实现特定的说明（CPython vs PyPy vs 其他）
- 🛠️ 用于估算你自己代码复杂度的 CLI 工具
- 🔍 交互式搜索和过滤
- 📱 移动端友好的响应式设计

## 网站

访问文档：[pythoncomplexity.com](https://pythoncomplexity.com)

---

## 快速开始

### 环境要求
- Python 3.10+（推荐 3.14）
- [uv](https://github.com/astral-sh/uv) - 快速的 Python 包管理器
- Git

### 安装

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and set up
git clone https://github.com/heikkitoivonen/python-time-space-complexity.git
cd python-time-space-complexity

# Install dependencies
uv sync

# Start development server
make serve
# Open http://localhost:8000
```

---

## 安装 Python Complexity 智能体技能

`python-complexity` 为智能体提供 Python 内置函数和标准库时间与空间复杂度的离线参考。
它可用于代码分析、性能审查和操作比较，并包含版本与实现相关的适用条件。
它独立于用于维护本仓库的技能。

从 [Python Complexity 技能发布页面](https://github.com/heikkitoivonen/python-time-space-complexity/releases)
下载 `python-complexity-<version>.zip` 和 `SHA256SUMS`。
选择标签为 `python-complexity-v<version>` 的发布版本。请使用发布附件中的技能 ZIP：
GitHub 自动生成的 **Source code** 压缩包以及源码目录 `skills/python-complexity/`
均不包含生成的参考文档。

解压 ZIP，将整个 `python-complexity` 目录放入以下位置之一。如有需要，先创建父目录。
每个智能体只选择一种安装范围，以免出现重复副本。

| 智能体 | 个人安装 | 项目安装 | 显式使用 |
|-------|-----------------------|----------------------|--------------|
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `~/.agents/skills/python-complexity/` | `.agents/skills/python-complexity/` | 输入 `$python-complexity`，后接问题 |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/python-complexity/` | `.claude/skills/python-complexity/` | 输入 `/python-complexity`，后接问题 |
| [GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) | `~/.copilot/skills/python-complexity/` | `.github/skills/python-complexity/` | 请 Copilot 使用 `python-complexity` 技能 |

`~` 表示主目录；在 Windows 上，请使用用户配置文件目录下的对应目录。
项目路径相对于要使用该技能的项目。云端智能体需要在其检出的项目中包含项目级安装；
本机上的个人目录不会传到云端。安装后的目录必须直接包含 `SKILL.md`、
`manifest.json`、`LICENSE.txt` 和 `references/`。
读取该技能不需要 Python、`uv`、Node.js 或网络访问。

例如，在 Linux 或 macOS 上，从下载目录为 Codex 安装 1.0.0 版本：

```bash
mkdir -p ~/.agents/skills
unzip python-complexity-1.0.0.zip -d ~/.agents/skills
```

使用 Linux 上的 `sha256sum`、macOS 上的 `shasum -a 256`，或 PowerShell 中的
`Get-FileHash -Algorithm SHA256`，将 ZIP 的 SHA-256 与 `SHA256SUMS` 中的对应条目比较。
启动新的智能体会话，然后提问，例如：“使用 python-complexity 分析此函数的时间复杂度和
峰值空间复杂度，并引用参考文档。”

### 更新或固定版本

更新时，请用新发布版本中的完整目录替换已安装的 `python-complexity` 目录，不要合并文件。
要固定版本，请保留该版本的 ZIP 及其校验和；安装目录中的 `manifest.json` 记录了技能版本、
源码修订版本和支持的 Python 版本。

### 卸载

1. 在上方的智能体表格中找到安装目录。例如，Codex 的个人安装目录为
   `~/.agents/skills/python-complexity/`。
2. 删除整个 `python-complexity` 目录，包括其中的参考文档。保留父级 `skills` 目录和
   其他技能。如果在个人和项目位置都安装了副本，请将两处副本都删除。
3. 启动新的智能体会话，以免继续使用已加载的技能指令。

如果项目级安装由 Git 跟踪，请提交目录删除操作，将卸载同步到其他检出副本。
通过解压 ZIP 安装的技能不需要使用包管理器的卸载命令。

## 开发命令

### 使用 Make（推荐）

```bash
make help                # See all available commands
make install             # Install production dependencies
make dev                 # Install dev environment
make serve               # Serve documentation locally, all locales
make serve-en            # Serve English documentation only
make serve-one LOCALE=ja  # Serve one locale as it ships
make build               # Build all locales as separate sites
make build-en            # Build English documentation only
make check               # Run lint, types, skill validation, and tests
make lint                # Check lint and formatting
make format              # Format code and apply lint fixes
make types               # Run type checker
make test                # Run tests
make audit               # Report live documentation coverage
make skills-build        # Build offline skill in build/skills/
make skills-check        # Validate generated skill content and links
make skills-package      # Create release ZIPs and checksums in dist/skills/
make skills-eval         # Build skill and display manual evaluation prompts
make clean               # Remove site output and development caches
make update              # Update dependencies
```

### 直接使用 uv

```bash
uv sync                    # Sync dependencies
uv run mkdocs serve        # Run command in venv
uv add package-name        # Add dependency
uv add --dev pytest-plugin # Add dev dependency
uv lock --upgrade          # Update dependencies
```

### 复杂度估算 CLI

测量你自己 Python 函数的 Big-O 复杂度：

```bash
# Usage: python scripts/estimate_complexity.py <module> <function>
python scripts/estimate_complexity.py my_script my_function
```

示例输出：
```text
Input Size (n)  | Avg Time (s)
-----------------------------------
100             | 0.000003
500             | 0.000012
...
Estimated Complexity: O(n) (Linear)
```

---

## 项目结构

```
├── docs/                       # MkDocs documentation source
│   ├── index.md                # Landing page
│   ├── builtins/               # Built-in types (list, dict, set, tuple, str)
│   ├── stdlib/                 # Standard library modules
│   ├── implementations/        # CPython, PyPy, Jython, IronPython
│   └── versions/               # Python version guides (3.10–3.14)
├── skills/                     # Distributable agent skill sources and release guidance
│   ├── python-complexity/
│   │   ├── SKILL.md            # Agent instructions
│   │   └── version.txt         # Independent skill release version
│   ├── README.md               # Build and distribution guide
│   └── evaluations.md          # Manual agent evaluation prompts and rubric
├── .agents/skills/             # Repository-maintenance skills (not distributed)
├── scripts/                    # Utility scripts
│   └── build_skills.py         # Generate, validate, and package the offline skill
├── tests/                      # Documentation, complexity, and packaging tests
├── build/skills/               # Generated installable skill (Git-ignored)
├── dist/skills/                # Generated release ZIPs and checksums (Git-ignored)
├── .github/workflows/          # GitHub Actions CI/CD
│   ├── deploy.yml             # Documentation site checks and deployment
│   └── skills.yml             # Skill checks, preview artifacts, and releases
├── pyproject.toml              # Project metadata and dependencies
├── mkdocs.yml                  # MkDocs configuration
└── Makefile                    # Development commands
```

---

## 开发流程

### 1. 创建特性分支
```bash
git checkout -b feature/add-numpy-complexity
```

### 2. 修改并在本地测试
```bash
vim docs/new-module.md
make serve  # View at http://localhost:8000
```

### 3. 运行质量检查
```bash
make lint    # Check code quality
make format  # Auto-format code
make types   # Type checking
make test    # Run tests
make check   # All checks (required before commit)
```

### 4. 提交并推送
```bash
git add .
git commit -m "Add: NumPy array complexity documentation"
git push origin feature/add-numpy-complexity
```

### 添加文档
1. 在 `docs/` 中创建 markdown 文件
2. 在 `mkdocs.yml` 导航中添加链接
3. 使用 `make serve` 本地测试
4. 提交前运行 `make check`

---

## 代码质量标准

### 代码检查与格式化
- **ruff** 用于代码检查（行长度：100 字符，Python 3.10+ 兼容）
- **pyright** 用于静态类型检查
- **pytest** 用于测试

### 提交信息
```
Type: Brief description

Types: Add, Fix, Update, Refactor, Docs, Test, Chore
Example: Add: List complexity documentation
```

---

## 快速参考 - Python 复杂度速查表

### 列表
| 操作 | 时间 | 备注 |
|-----------|------|-------|
| `append()` | O(1)* | 均摊 |
| `insert(i)` | O(n) | 移动元素 |
| `pop()` | O(1) | 最后一个元素 |
| `pop(0)` | O(n) | 第一个元素 |
| `in` | O(n) | 线性查找 |
| `sort()` | O(n log n) | Timsort/Powersort |

**小贴士：** 使用 `deque.appendleft()` 进行 O(1) 前插，而不是 `list.insert(0)`。

### 字典与集合
| 操作 | 时间 |
|-----------|------|
| `d[key]` | 平均 O(1) |
| `d[key] = v` | 平均 O(1) |
| `key in d` | 平均 O(1) |
| `set.add()` | 平均 O(1) |
| `x in set` | 平均 O(1) |

**小贴士：** 使用 set 进行快速的成员检测，而不是 list。

### 字符串
| 操作 | 时间 |
|-----------|------|
| `len()` | O(1) |
| `s[i]` | O(1) |
| `in`（子串） | 平均 O(n) |
| `split()` / `join()` | O(n) |

**小贴士：** 在循环中使用 `"".join(list)`，不要使用 `+=`。

### 标准库

| 模块 | 操作 | 时间 |
|--------|-----------|------|
| **deque** | `append()` / `appendleft()` | O(1) |
| **deque** | `pop()` / `popleft()` | O(1) |
| **heapq** | `heapify()` | O(n) |
| **heapq** | `heappush()` / `heappop()` | O(log n) |
| **bisect** | `bisect_left/right()` | O(log n) |

### 常见模式

```python
# ❌ Bad: O(n) membership check
if item in list: pass

# ✅ Good: O(1) membership check
if item in set: pass

# ❌ Bad: O(n²) string concatenation
result = ""
for item in items:
    result += item

# ✅ Good: O(n) string building
result = "".join(items)

# ❌ Bad: O(n) prepend
lst.insert(0, item)

# ✅ Good: O(1) prepend
from collections import deque
dq = deque()
dq.appendleft(item)
```

### Python 版本性能
```
Python 3.10     ← Baseline
Python 3.11     ← +10-60% improvements (inline caching!)
Python 3.12     ← +5-10% improvements
Python 3.13     ← Similar (experimental free-threading)
Python 3.14     ← Better GC pauses, new heapq max-heap
```

### 实现对比
| 实现 | 使用场景 | 速度 | GIL |
|---|---|---|---|
| CPython | 默认，标准 | 好 | 有 |
| PyPy | CPU 密集型循环 | 优秀* | 无 |
| Jython | Java 集成 | 好 | 无 |
| IronPython | .NET 集成 | 好 | 无 |

---

## 部署

### GitHub Pages 设置
1. 推送到 GitHub
2. 前往 **Settings** → **Pages**
3. 选择 **Deploy from a branch** → **gh-pages**
4. GitHub Actions 会在推送时自动部署

### 自定义域名（可选）
1. 更新 `mkdocs.yml` 中的 `site_url`
2. 配置 DNS 指向 GitHub Pages
3. 在 GitHub Settings → Pages 中输入自定义域名
4. 启用 HTTPS

---

## 故障排查

### 构建问题
```bash
make clean && make build
uv run mkdocs serve --verbose
```

### 依赖问题
```bash
rm -rf .venv/ && uv sync
```

### GitHub Pages 未更新
1. 检查 GitHub Actions 选项卡中的错误
2. 确认 gh-pages 分支存在
3. 等待约 1-2 分钟完成部署

---

## 来源与参考

- [Python 官方文档](https://docs.python.org/3/)
- [TimeComplexity Wiki](https://wiki.python.org/moin/TimeComplexity)
- [Python 增强提案（PEPs）](https://www.python.org/dev/peps/)
- [uv 文档](https://docs.astral.sh/uv/)
- [MkDocs 文档](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)

## 参与贡献

欢迎贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 许可证

MIT 许可证 - 详见 [LICENSE.txt](LICENSE.txt)

## 免责声明

虽然我们力求准确，但复杂度信息可能因具体实现和版本而异。对于性能关键代码，请务必参考官方文档和基准测试进行验证。

---

⭐ 如果你觉得本仓库有用，**请给它点个 Star**——这能帮助更多人发现它。
