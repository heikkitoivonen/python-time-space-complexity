# Documentation Coverage Status

This document tracks the coverage of built-in functions, types, and standard library modules that need documentation.

## Overview

- **Total Items**: 317 (150 builtins + 167 stdlib modules)
- **Documented**: 389 (174 builtins + 215 stdlib)
- **Coverage**: 122.7%

**Note**: Coverage exceeds 100% because comprehensive documentation files (like `exceptions.md`) cover multiple individual items, and we document deprecated/removed modules for historical reference.

Last updated: January 30, 2026 (Python 3.14 audit)

## Built-in Types & Functions

**Coverage: 116.0% (174/150)**

All 150 built-in functions, types, and constants are fully documented, with comprehensive guides for multiple related items.

### ✅ Documented (174 items covering 150 builtins)
- `bool`
- `bytes`
- `dict`
- `frozenset`
- `list`
- `range`
- `set`
- `str`
- `tuple`
- `int`
- `float`
- `type`
- `len()`
- `max()`
- `min()`
- `sum()`
- `map()`
- `filter()`
- `zip()`
- `sorted()`
- `enumerate()`
- `all()`
- `any()`
- `abs()`
- `pow()`
- `round()`
- `ord()`
- `chr()`
- `reversed()`
- `divmod()`
- `slice()`
- `isinstance()`
- `iter()`
- `format()`
- `issubclass()`
- `open()`
- `hash()`
- `next()`
- `input()`
- `id()`
- `globals()`
- `locals()`
- `print()`
- `help()`
- `repr()`
- `ascii()`
- `eval()`
- `exec()`
- `compile()`
- `hex()`
- `bin()`
- `oct()`
- `callable()`
- `bool()` - Convert to boolean
- `int()` - Convert to integer
- `float()` - Convert to floating-point
- `str()` - Convert to string
- `bytes()` - Convert to bytes
- `list()` - Create/convert to list
- `dict()` - Create/convert to dictionary
- `set()` - Create set
- `frozenset()` - Create immutable set
- `tuple()` - Create/convert to tuple
- `bytearray()` - Mutable bytes
- `complex()` - Create complex number
- `memoryview()` - Create memory view
- `object()` - Base class object
- `dir()` - List attributes
- `getattr()` - Get attribute value
- `hasattr()` - Check attribute existence
- `setattr()` - Set attribute value
- `delattr()` - Delete attribute
- `vars()` - Get __dict__
- `classmethod()` - Class method decorator
- `staticmethod()` - Static method decorator
- `property()` - Property descriptor
- `super()` - Call parent class method
- `None` - Null value
- `True` - Boolean true
- `False` - Boolean false
- `NotImplemented` - Not implemented marker
- `Ellipsis` (`...`) - Ellipsis object
- **Exceptions** (comprehensive guide covering 40+ core exceptions)

### ❌ Priority Missing (Major built-ins - Next batch)

These are frequently used and should be documented next:

(All priority missing built-ins have been documented!)

### ✅ Exceptions (40+ - FULLY DOCUMENTED)

All core exceptions documented in comprehensive guide:

- ✅ `Exception` - Base class for most exceptions
- ✅ `ValueError` - Inappropriate argument value
- ✅ `TypeError` - Inappropriate argument type
- ✅ `KeyError` - Dictionary key not found
- ✅ `IndexError` - Sequence index out of range
- ✅ `RuntimeError` - Generic runtime error
- ✅ `OSError` - OS-level errors
- ✅ `FileNotFoundError` - File not found
- ✅ `ZeroDivisionError` - Division by zero
- ✅ `AttributeError` - Attribute not found
- ✅ `NameError` - Name not found
- ✅ `ImportError` / `ModuleNotFoundError` - Import failed
- ✅ `AssertionError` - Assertion failed
- ✅ `NotImplementedError` - Not implemented
- ✅ `StopIteration` - Iterator exhausted
- ✅ `EOFError` - End of file
- ✅ `KeyboardInterrupt` - User interrupt
- ✅ `MemoryError` - Out of memory
- ✅ Plus 20+ more in exception hierarchy

### ✅ All Built-ins Documented

Complete coverage of all built-in functions, types, exceptions, and constants:

**Type Conversion Functions (0/7 - COMPLETE)**
- ✅ `bool()` - Convert to boolean
- ✅ `int()` - Convert to integer
- ✅ `float()` - Convert to floating-point
- ✅ `str()` - Convert to string
- ✅ `bytes()` - Convert to bytes
- ✅ `list()` - Create/convert to list
- ✅ `dict()` - Create/convert to dictionary

**Container & Iteration Functions (7/7 - COMPLETE)**
- ✅ `set()` - Create set
- ✅ `frozenset()` - Create immutable set
- ✅ `tuple()` - Create/convert to tuple
- ✅ `memoryview()` - Create memory view
- ✅ `bytearray()` - Mutable bytes
- ✅ `complex()` - Create complex number
- ✅ `object()` - Base class object
- (range() - Already documented in Built-in Types)

**Object Introspection (7/7 - COMPLETE)**
- ✅ `dir()` - List attributes/names
- ✅ `getattr()` - Get attribute value
- ✅ `hasattr()` - Check attribute existence
- ✅ `setattr()` - Set attribute value
- ✅ `delattr()` - Delete attribute
- ✅ `vars()` - Get __dict__
- ✅ `type()` - Already documented

**Class & Function Decorators (3/3 - COMPLETE)**
- ✅ `classmethod()` - Class method decorator
- ✅ `staticmethod()` - Static method decorator
- ✅ `property()` - Property descriptor

**Object & Inheritance (2/2 - COMPLETE)**
- ✅ `super()` - Call parent class method
- ✅ `isinstance()` - Already documented

**Built-in Constants & Special Objects (5/5 - COMPLETE)**
- ✅ `None` - Null value
- ✅ `True` - Boolean true
- ✅ `False` - Boolean false
- ✅ `NotImplemented` - Not implemented marker
- ✅ `Ellipsis` (`...`) - Ellipsis object

**Async Functions (2/2 - COMPLETE)**
- ✅ `aiter()` - Create async iterator
- ✅ `anext()` - Get next async item

**Debugging & System (3/3 - COMPLETE)**
- ✅ `breakpoint()` - Drop into debugger
- ✅ `exit()` - Exit interpreter
- ✅ `quit()` - Exit interpreter

**Interpreter Information (3/3 - COMPLETE)**
- ✅ `copyright` - Python copyright notice
- ✅ `credits` - Python credits
- ✅ `license` - Python license

**All Exception Classes (68/68 - COMPLETE)**
- ✅ Comprehensive guide covering all 68 exception classes, warnings, and hierarchy
- ✅ All exception handling patterns and best practices documented

---

## Standard Library Modules

**Coverage: 128.7% (215/167)**

All standard library modules are fully documented, including new Python 3.14 modules. Coverage exceeds 100% due to documentation of deprecated/removed modules for historical reference.

### ✅ Python 3.14 Modules (NEW)

- ✅ `annotationlib` - Annotation introspection (PEP 649/749)
- ✅ `compression` - Unified compression package with zstd support
- ✅ `turtledemo` - Turtle graphics demonstrations

### ✅ Recently Added

- ✅ `warnings` - Warning message system
- ✅ `secrets` - Cryptographic random number generation
- ✅ `tomllib` - TOML file parser
- ✅ `tracemalloc` - Memory allocation tracing
- ✅ `cgi` - CGI utilities
- ✅ `cgitb` - CGI traceback utility
- ✅ `imp` - Import machinery (deprecated)
- ✅ `plistlib` - Property list format
- ✅ `sndhdr` - Sound file format detection
- ✅ `select` - I/O multiplexing

### ⊘ Excluded Items (4 - intentionally out of scope)

These items appear in audit but are **intentionally not documented** as they are not part of Python's standard library:

**Project Scripts** (not stdlib):
- `audit_documentation` - Project's own audit script
- `introspect` - Project's introspection script

**Third-party Packages** (external, not stdlib):
- `pip` - External package manager

**Case Sensitivity**:
- `cProfile` - Already documented as `cprofile.md`

### ✅ Priority Tier 1 Complete (9/9 - 100%)

All priority stdlib modules now documented:
- ✅ `argparse` - Command-line argument parsing
- ✅ `logging` - Logging facility
- ✅ `sqlite3` - SQLite database interface
- ✅ `subprocess` - Subprocess management
- ✅ `threading` - Thread-based parallelism
- ✅ `socket` - Network socket interface
- ✅ `pathlib` - Object-oriented filesystem paths (already exists in nav)
- ✅ `re` - Regular expressions (already exists in nav)
- ✅ `unittest` - Unit testing framework

### ✅ Data Structures & Algorithms (12/12 - COMPLETE)

All data structure modules now documented:
- ✅ `array` - Efficient arrays
- ✅ `deque` - Double-ended queue
- ✅ `defaultdict` - Default value dictionaries
- ✅ `Counter` - Counting hashable objects
- ✅ `OrderedDict` - Ordered dictionaries
- ✅ `namedtuple` - Tuple with named fields
- ✅ `bisect` - Binary search algorithms
- ✅ `heapq` - Heap queue operations
- ✅ `queue` - Thread-safe queues
- ✅ `collections` - Container data types
- ✅ `copy` - Object copying
- ✅ `graphlib` - Topological sorting

### ✅ Compression & Encoding (8/8 - COMPLETE)

All compression and encoding modules now documented:
- ✅ `zipfile` - ZIP archive handling
- ✅ `tarfile` - TAR archive handling
- ✅ `gzip` - GZIP compression
- ✅ `bz2` - BZIP2 compression
- ✅ `zlib` - DEFLATE compression
- ✅ `lzma` - XZ compression
- ✅ `hmac` - Message authentication codes
- ✅ `codecs` - Character encoding/decoding

### ✅ Async & Concurrency (11/11 - COMPLETE)

All async/concurrency modules now documented:
- ✅ `asyncio` - Asynchronous I/O
- ✅ `asynchat` - Async chat utilities (deprecated, removed in 3.13)
- ✅ `asyncore` - Async socket dispatcher (deprecated, removed in 3.13)
- ✅ `concurrent.futures` - Executor-based parallelism
- ✅ `contextvars` - Context variables for async
- ✅ `multiprocessing` - Process-based parallelism
- ✅ `selectors` - Multiplexed I/O
- ✅ `signal` - Signal handling
- ✅ `threading` - Thread-based parallelism
- ✅ `queue` - Thread-safe queues
- ✅ Core patterns and relationships documented

### ✅ File & IO Operations (6/6 - COMPLETE)

All file and I/O modules now documented:
- ✅ `fileinput` - Process file lines
- ✅ `genericpath` - Generic path utilities
- ✅ `ntpath` - Windows path operations
- ✅ `posixpath` - Unix path operations
- ✅ `shutil` - High-level file operations
- ✅ `tempfile` - Temporary files

### ✅ ALL MODULES COMPLETE (215/215)

All 112 previously undocumented stdlib modules have been added:

**Utilities & System (22)**
- ✅ `ast` - Abstract syntax trees
- ✅ `dis` - Disassembler for bytecode
- ✅ `doctest` - Testing via docstrings
- ✅ `errno` - Error number constants
- ✅ `gc` - Garbage collection interface
- ✅ `getopt` - Command-line option parsing
- ✅ `gettext` - Internationalization
- ✅ `keyword` - Python keywords
- ✅ `linecache` - Cache module source
- ✅ `optparse` - Option parsing (deprecated)
- ✅ `pdb` - Python debugger
- ✅ `profile` - Performance profiling
- ✅ `cProfile` - C-based profiling
- ✅ `pstats` - Profile statistics
- ✅ `pydoc` - Documentation viewer
- ✅ `runpy` - Run Python modules
- ✅ `sched` - Event scheduler
- ✅ `select` - I/O multiplexing
- ✅ `stat` - File status constants
- ✅ `sysconfig` - System configuration
- ✅ `syslog` - System logger
- ✅ `trace` - Trace execution

**String & Text Processing (4)**
- ✅ `stringprep` - Unicode preparation
- ✅ `reprlib` - Alternative repr()
- ✅ `quopri` - Quoted-printable encoding
- ✅ `uu` - Uuencoding

**Data Serialization (3)**
- ✅ `mailbox` - Mailbox formats
- ✅ `mailcap` - Mailcap file handling
- ✅ `pickletools` - Pickle disassembler

**Audio & Media (3)**
- ✅ `aifc` - AIFF/AIFC audio files
- ✅ `sunau` - Sun AU audio files
- ✅ `wave` - WAV audio files

**Network & Internet (11)**
- ✅ `ftplib` - FTP client
- ✅ `http` - HTTP protocol
- ✅ `imaplib` - IMAP4 protocol
- ✅ `nntplib` - NNTP protocol
- ✅ `poplib` - POP3 protocol
- ✅ `smtpd` - SMTP server
- ✅ `socketserver` - Socket server
- ✅ `ssl` - SSL/TLS support
- ✅ `telnetlib` - Telnet client
- ✅ `xmlrpc` - XML-RPC protocol

**File & Path Operations (9)**
- ✅ `chunk` - IFF chunk reading
- ✅ `imghdr` - Image file type detection
- ✅ `nturl2path` - URL to path conversion
- ✅ `pipes` - Shell pipeline interface
- ✅ `posix` - POSIX APIs (low-level)
- ✅ `pty` - Pseudo-terminal
- ✅ `pwd` - Unix password database
- ✅ `tty` - Terminal control
- ✅ `zipimport` - Zip import support

**Memory Mapping (1)**
- ✅ `mmap` - Memory-mapped file access

**Parsing & Compilation (13)**
- ✅ `codeop` - Compile Python source
- ✅ `code` - Code evaluation
- ✅ `py_compile` - Compilation
- ✅ `pyexpat` - Low-level Expat XML parser
- ✅ `lib2to3` - Python 2 to 3 conversion
- ✅ `modulefinder` - Module dependencies
- ✅ `opcode` - Python opcodes
- ✅ `pyclbr` - Class/function browser
- ✅ `sre_compile` - Regular expression compilation
- ✅ `sre_constants` - Regex constants
- ✅ `sre_parse` - Regex parsing
- ✅ `symtable` - Symbol table
- ✅ `token` - Token types

**Number Operations (2)**
- ✅ `math` - Floating-point math functions
- ✅ `zoneinfo` - IANA time zone database

**GUI & Interface (4)**
- ✅ `curses` - Terminal control (Unix)
- ✅ `idlelib` - IDLE editor library
- ✅ `tkinter` - Tk GUI toolkit
- ✅ `turtle` - Turtle graphics

**Build & Installation (5)**
- ✅ `distutils` - Distribution utilities
- ✅ `ensurepip` - Pip installation
- ✅ `venv` - Virtual environments
- ✅ `wsgiref` - WSGI utilities
- ✅ `zipapp` - ZIP application creation

**Development & Meta (9)**
- ✅ `antigravity` - Easter egg
- ✅ `bdb` - Debugger framework
- ✅ `cmd` - Interactive command interfaces
- ✅ `compileall` - Batch compilation
- ✅ `pydoc_data` - Pydoc data
- ✅ `rlcompleter` - Readline completion
- ✅ `tabnanny` - Python indentation checker
- ✅ `this` - Zen of Python
- ✅ `readline` - Line-editing support

**System & Locale (7)**
- ✅ `netrc` - Netrc file handling
- ✅ `site` - Site-specific configuration
- ✅ `crypt` - Password hashing (Unix)
- ✅ `fcntl` - File control (Unix)
- ✅ `termios` - POSIX terminal I/O control
- ✅ `resource` - Process resource limits (Unix)
- ✅ `grp` - Unix group database

**Internal & Testing (11)**
- ✅ `concurrent` - Concurrency (parent package)
- ✅ `copyreg` - Copy registration
- ✅ `encodings` - Built-in encodings
- ✅ `xdrlib` - XDR serialization
- ✅ `xml` - XML parsing base
- ✅ `xml.dom` - DOM XML APIs
- ✅ `xml.sax` - SAX XML APIs
- ✅ `xml.etree.ElementTree` - ElementTree XML APIs
- ✅ `binascii` - Binary-ASCII conversion
- ✅ `marshal` - Object serialization
- ✅ `webbrowser` - Browser control

---

## Contribution Process

### Claiming a Module/Built-in

1. Find the item you want to document in the lists above
2. Create a branch: `docs/{category}/{name}` (e.g., `docs/stdlib/os`)
3. Create documentation following the template
4. Add entry to `mkdocs.yml` navigation
5. Submit PR with clear description

### Documentation Template

Create files following this structure (example: `docs/stdlib/os.md`):

```markdown
# os module

Brief description of the module.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| ... | ... | ... | ... |

## Common Operations

### os.path.join()
- Description
- Complexity details
- Example code

## Related Modules
- Link to related docs
```

### Verification Steps

Before submitting:

1. Run audit to verify: `python scripts/audit_documentation.py`
2. Run tests: `make test`
3. Ensure coverage doesn't decrease
4. Check linting: `make lint`

---

## Coverage Goals

### Phase 1 (Foundation - 50+ items)
- All major built-in types and functions
- Top 20 stdlib modules
- Target: ~20% coverage

### Phase 2 (Expansion - 100+ items)
- Additional built-in functions and exceptions
- Common stdlib modules
- Target: ~40% coverage

### Phase 3 (Completeness - 379 items)
- All documented modules
- Target: 100% coverage

---

## Tracking

- **Audit Report**: `data/documentation_audit.json` (auto-generated)
- **Run Audit**: `python scripts/audit_documentation.py`
- **Run Tests**: `make test`

### Audit Report Structure

```json
{
  "builtins": {
    "total": 150,
    "documented": 8,
    "coverage_percent": 5.3,
    "missing": ["ArithmeticError", "..."],
    "by_category": {...}
  },
  "stdlib": {
    "total": 168,
    "documented": 6,
    "coverage_percent": 3.6,
    "missing": ["abc", "..."]
  },
  "summary": {
    "total_items": 318,
    "total_documented": 14,
    "overall_coverage_percent": 4.4
  }
}
```

---

## FAQ

**Q: How do I document a new module?**
A: Use the template above. Copy an existing doc like `docs/stdlib/itertools.md` and adapt it.

**Q: How does audit detection work?**
A: The script scans `docs/builtins/` and `docs/stdlib/` directories and compares against Python's actual builtins and stdlib modules using `pkgutil` and `inspect`.

**Q: What happens if coverage decreases?**
A: Tests will fail (`test_minimum_builtin_coverage`, `test_minimum_stdlib_coverage`). The minimum is set to prevent regression.

**Q: How do I update the audit?**
A: Run `python scripts/audit_documentation.py` before committing. It regenerates `data/documentation_audit.json`.
