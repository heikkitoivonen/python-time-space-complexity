# pydoc_data Module Complexity

The `pydoc_data` package holds the data behind [pydoc](pydoc.md)'s interactive help that cannot
be read from docstrings. `pydoc_data.topics` is one dict of help texts for keywords, symbols and
language topics - what `help('with')` or `help('FORMATTING')` shows - generated from the Python
documentation when the release is built. From Python 3.13.12 and 3.14.3, `pydoc_data.module_docs`
maps standard-library module names to their pages on docs.python.org. The package also ships
`_pydoc.css`, the stylesheet the `pydoc -b` browser serves.

The texts are loaded all at once: the first import of `pydoc_data.topics` builds every string in
it, and they stay in memory for the life of the process. `import pydoc` does not load them;
`pydoc` imports the module the first time a topic is shown. The package is undocumented, and its
contents change with every release.

`T` is the characters in all the topic texts together, fixed for a given release; `u` is the
topic labels; `x` is the characters in one topic's text; and `m` is the entries in
`module_docs`. Dictionary lookups are O(1).

## Complexity Reference

### pydoc_data

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import pydoc_data` | O(1) | O(1) | An empty package; importing it loads no data |

### topics

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import pydoc_data.topics` | O(T) | O(T) | The first import builds every topic text; later imports find it in `sys.modules` in O(1) |
| `pydoc_data.topics.topics[label]` | O(1) | O(1) | Returns the stored string itself. Labels are `pydoc`'s own, such as `'with'` or `'typesseq'` |
| Iterating `pydoc_data.topics.topics` | O(u) | O(1) | `len()` is O(1) |
| `help('with')`, `pydoc.Helper.help(request)` for a keyword, symbol or topic | O(T) on the first topic, then O(x) | O(T), then O(x) | Imports `pydoc_data.topics` on first use, then formats one text |

### module_docs

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `import pydoc_data.module_docs` | O(m) | O(m) | Python 3.13.12+ and 3.14.3+; `pydoc` imports it only to link a standard-library module to its online page |
| `pydoc_data.module_docs.module_docs[name]` | O(1) | O(1) | A page and anchor such as `'json#module-json'`, relative to the documentation root |

## Looking Up a Topic

A lookup is one dict access, but the first import pays for every text in the release. That is
why `pydoc` defers it until a topic is asked for.

```python
import sys

import pydoc_data.topics  # O(T) the first time - every topic text at once

topics = pydoc_data.topics.topics
text = topics['with']  # O(1)
assert text.lstrip().startswith('The "with" statement')
assert topics['with'] is text  # the stored string, not a copy
assert 'pydoc_data.topics' in sys.modules  # a later import is O(1)
```

### When pydoc Loads the Texts

`import pydoc` leaves the topics alone. The first `help()` call for a keyword, symbol or topic
imports them; every later one formats a single text.

```python
import contextlib
import io
import sys

import pydoc

assert 'pydoc_data.topics' not in sys.modules  # O(1) - nothing loaded yet

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    pydoc.Helper(output=buffer).help('with')  # O(T) the first time, then O(x)

assert 'pydoc_data.topics' in sys.modules
assert 'The "with" statement' in buffer.getvalue()
```

## Linking to the Online Documentation

`module_docs` exists only on patch releases from 3.13.12 and 3.14.3, so look for it rather than
testing the version.

```python
import importlib.util

if importlib.util.find_spec('pydoc_data.module_docs') is not None:
    from pydoc_data.module_docs import module_docs  # O(m)

    assert module_docs['json'] == 'json#module-json'  # O(1)
```

## Performance Best Practices

✅ **Do**:

- Read `pydoc_data.topics.topics` directly when you need the texts as data; it is the same dict
  `help()` reads
- Expect the first keyword or topic `help()` in a process to be the slow one

❌ **Avoid**:

- Importing `pydoc_data.topics` in a program that never shows help - its texts stay loaded for the
  rest of the process
- Relying on a particular label or text; both are regenerated for every release

## Version Notes

- **Python 3.13.12+, 3.14.3+**: `pydoc_data.module_docs`, which `pydoc` uses to link a
  standard-library module to its page on docs.python.org
- **All Python 3**: Undocumented; the topic texts are regenerated for each release

## Related Modules

- **[pydoc](pydoc.md)** - the `help()` system that reads this data
- **[keyword](keyword.md)** - the keyword list, without the help texts
