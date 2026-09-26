# gettext Module Complexity

The `gettext` module looks up translated messages in GNU `.mo` catalogs. Loading a catalog reads
the whole file and decodes every message into a dictionary, once; after that a lookup is a
dictionary probe. `translation()` keeps each parsed catalog for the life of the process, but the
module-level `gettext()` family calls `translation()` again for every message, so each call repeats
the search for catalog files.

`k` is the characters in the message id being looked up, the context included for the `p`
variants; `b` is the bytes in the `.mo` files a call parses; `f` is the catalogs in a fallback
chain; `d` is the candidates `find()` considers, which is every requested language expanded
into its locale variants (up to eight per language), each at most one existence check. A filesystem existence check and one
evaluation of a catalog's plural formula are treated as O(1).

## Complexity Reference

### Module-level functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gettext.bindtextdomain(domain, localedir=None)` | O(1) | O(1) | Records where the module-level functions look for `domain`, and returns the current binding |
| `gettext.textdomain(domain=None)` | O(1) | O(1) | Sets or returns the domain `gettext()`, `ngettext()`, `pgettext()` and `npgettext()` use |
| `gettext.gettext(message)`, `gettext.dgettext(domain, message)`, `gettext.ngettext(msgid1, msgid2, n)`, `gettext.dngettext(domain, msgid1, msgid2, n)` | O(d² + b + f·k) | O(d + b) | Each call runs `translation()` again, so the file search repeats; b is zero once the catalogs are cached. With no catalog found, the message comes back unchanged |
| `gettext.pgettext(context, message)`, `gettext.dpgettext(domain, context, message)`, `gettext.npgettext(context, msgid1, msgid2, n)`, `gettext.dnpgettext(domain, context, msgid1, msgid2, n)` | O(d² + b + f·k) | O(d + b + f·k) | As above, and the context key is built again on every call |

### find and translation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gettext.find(domain, localedir=None, languages=None, all=False)` | O(d²) | O(d) | At most one existence check per candidate, stopping at the first hit unless `all=True`; candidates are deduplicated by list scan. Languages default to `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` or `LANG`, and a `C` entry ends the search |
| `gettext.translation(domain, localedir=None, languages=None, class_=None, fallback=False)` | O(d² + b) | O(d + b) | b counts only files not parsed before: catalogs are cached per class and absolute path for the life of the process, and a changed file is not reread. Returns a copy chaining every catalog found; raises `FileNotFoundError` when there is none, unless `fallback=True` |
| `gettext.install(domain, localedir=None, *, names=None)` | O(d² + b + p) | O(d + b + p) | `translation(..., fallback=True)` followed by its `install(names)` |

### NullTranslations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gettext.NullTranslations(fp=None)` | O(1) | O(1) | Does not read `fp`: its `_parse()` does nothing |
| `NullTranslations._parse(fp)` | O(1) | O(1) | The hook a subclass overrides to read another catalog format; the constructor calls it when `fp` is given |
| `NullTranslations.gettext(message)`, `NullTranslations.ngettext(msgid1, msgid2, n)`, `NullTranslations.pgettext(context, message)`, `NullTranslations.npgettext(context, msgid1, msgid2, n)` | O(1) | O(1) | Returns the message unchanged, `msgid1` or `msgid2` by whether `n == 1`; with a fallback added, the call is the fallback's |
| `NullTranslations.add_fallback(fallback)` | O(f) | O(f) | Walks to the end of the chain and appends there |
| `NullTranslations.info()` | O(1) | O(1) | The catalog's header dictionary itself, not a copy |
| `NullTranslations.charset()` | O(1) | O(1) | From the catalog's `Content-Type` header; `None` without a catalog |
| `NullTranslations.install(names=None)` | O(1 + p) | O(1 + p) | p = names passed; binds `_` in `builtins`, plus whichever of `gettext`, `ngettext`, `pgettext` and `npgettext` are named |

### GNUTranslations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `gettext.GNUTranslations(fp)`, `GNUTranslations._parse(fp)` | O(b) | O(b) | Reads the whole file and decodes every message; raises `OSError` for a bad magic number or version, or a message that runs past the end |
| `GNUTranslations.gettext(message)`, `GNUTranslations.ngettext(msgid1, msgid2, n)` | O(k) | O(1) | A hit compares the message id with the stored one. A miss repeats the call on the fallback, so a chain of f catalogs costs O(f·k) time and O(f) space |
| `GNUTranslations.pgettext(context, message)`, `GNUTranslations.npgettext(context, msgid1, msgid2, n)` | O(k) | O(k) | The context key is built on every call; a miss repeats that on the fallback, O(f·k) time and space |

## Loading a Catalog

### Parsing Reads the Whole File

`GNUTranslations` decodes every message in the file when it is built, whether or not any of them
is ever asked for. It needs only an object with `read()`, so a catalog can come from memory.

```python
import gettext
import io
import struct

def make_mo(messages):
    """Encode {msgid: msgstr} as a little-endian GNU .mo file."""
    entries = sorted({"": "Content-Type: text/plain; charset=UTF-8\n", **messages}.items())
    count = len(entries)
    tables, strings = [b"", b""], b""
    for column in (0, 1):
        for entry in entries:
            data = entry[column].encode()
            tables[column] += struct.pack("<2I", len(data), 28 + 16 * count + len(strings))
            strings += data + b"\0"
    header = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + 8 * count, 0, 0)
    return header + tables[0] + tables[1] + strings

catalog = gettext.GNUTranslations(io.BytesIO(make_mo({"Hello": "Hei"})))  # O(b)
assert catalog.gettext("Hello") == "Hei"  # O(k)
assert catalog.gettext("Goodbye") == "Goodbye"  # a miss returns the message
assert catalog.charset() == "UTF-8"  # O(1)
assert catalog.info() is catalog.info()  # O(1) - the header dictionary itself

try:
    gettext.GNUTranslations(io.BytesIO(b"not a catalog"))
except OSError as error:
    assert "Bad magic number" in str(error)
else:
    raise AssertionError("a file without the magic number was parsed")
```

### The Catalog Cache

`translation()` searches for files every time, but parses each one only once per process: later
calls get a copy that shares the parsed messages. The cache is never checked against the file, so
a catalog rewritten while the program runs is not seen until it restarts.

```python
import gettext
import pathlib
import struct
import tempfile

def make_mo(messages):
    """Encode {msgid: msgstr} as a little-endian GNU .mo file."""
    entries = sorted({"": "Content-Type: text/plain; charset=UTF-8\n", **messages}.items())
    count = len(entries)
    tables, strings = [b"", b""], b""
    for column in (0, 1):
        for entry in entries:
            data = entry[column].encode()
            tables[column] += struct.pack("<2I", len(data), 28 + 16 * count + len(strings))
            strings += data + b"\0"
    header = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + 8 * count, 0, 0)
    return header + tables[0] + tables[1] + strings

with tempfile.TemporaryDirectory() as localedir:
    mofile = pathlib.Path(localedir, "fi", "LC_MESSAGES", "app.mo")
    mofile.parent.mkdir(parents=True)
    mofile.write_bytes(make_mo({"Hello": "Hei"}))

    assert gettext.find("app", localedir, ["fi"]) == str(mofile)  # O(d²)

    first = gettext.translation("app", localedir, ["fi"])  # O(d² + b) - parses
    second = gettext.translation("app", localedir, ["fi"])  # O(d²) - cached
    assert first is not second and first.info() is second.info()

    mofile.write_bytes(make_mo({"Hello": "Moi"}))
    assert gettext.translation("app", localedir, ["fi"]).gettext("Hello") == "Hei"

    # No catalog: an error, or a NullTranslations when asked for one
    try:
        gettext.translation("app", localedir, ["de"])
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("a missing catalog was found")
    null = gettext.translation("app", localedir, ["de"], fallback=True)
    assert type(null) is gettext.NullTranslations
    assert null.gettext("Hello") == "Hello"
```

## Looking Up Messages

### Bind Once, Not Per Message

`gettext.gettext()` and its siblings take no catalog: each call runs `translation()` for the
current domain, searching the candidate directories again before the dictionary probe. Binding
the lookup once pays for the search once, and every hit after that costs O(k).

```python
import gettext
import os
import pathlib
import struct
import tempfile

def make_mo(messages):
    """Encode {msgid: msgstr} as a little-endian GNU .mo file."""
    entries = sorted({"": "Content-Type: text/plain; charset=UTF-8\n", **messages}.items())
    count = len(entries)
    tables, strings = [b"", b""], b""
    for column in (0, 1):
        for entry in entries:
            data = entry[column].encode()
            tables[column] += struct.pack("<2I", len(data), 28 + 16 * count + len(strings))
            strings += data + b"\0"
    header = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + 8 * count, 0, 0)
    return header + tables[0] + tables[1] + strings

with tempfile.TemporaryDirectory() as localedir:
    mofile = pathlib.Path(localedir, "fi", "LC_MESSAGES", "app.mo")
    mofile.parent.mkdir(parents=True)
    mofile.write_bytes(make_mo({"Hello": "Hei"}))
    os.environ["LANGUAGE"] = "fi"

    gettext.bindtextdomain("app", localedir)  # O(1)
    gettext.textdomain("app")  # O(1)

    # PER CALL: O(d² + f·k), plus O(b) the first time - the search runs for every message
    assert gettext.gettext("Hello") == "Hei"

    # ONCE: O(d² + b), then O(k) per message
    _ = gettext.translation("app", localedir).gettext
    assert _("Hello") == "Hei"
```

### Plural Forms and Context

`ngettext()` asks the catalog's plural formula which form a count takes, then looks that form up;
`pgettext()` joins the context to the message to make the key, which it does again on every call.

```python
import gettext
import io
import struct

def make_mo(messages):
    """Encode {msgid: msgstr} as a little-endian GNU .mo file."""
    entries = sorted({"": "Content-Type: text/plain; charset=UTF-8\n", **messages}.items())
    count = len(entries)
    tables, strings = [b"", b""], b""
    for column in (0, 1):
        for entry in entries:
            data = entry[column].encode()
            tables[column] += struct.pack("<2I", len(data), 28 + 16 * count + len(strings))
            strings += data + b"\0"
    header = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + 8 * count, 0, 0)
    return header + tables[0] + tables[1] + strings

catalog = gettext.GNUTranslations(io.BytesIO(make_mo({
    "": "Content-Type: text/plain; charset=UTF-8\nPlural-Forms: nplurals=2; plural=n != 1;\n",
    "file\0files": "tiedosto\0tiedostoa",  # msgid1 NUL msgid2: form 0 NUL form 1
    "menu\x04Open": "Avaa",  # context EOT message
})))

assert catalog.ngettext("file", "files", 1) == "tiedosto"  # O(k)
assert catalog.ngettext("file", "files", 3) == "tiedostoa"  # O(k)
assert catalog.pgettext("menu", "Open") == "Avaa"  # O(k) - builds "menu\x04Open"
assert catalog.pgettext("door", "Open") == "Open"  # another context misses
```

### Fallback Chains

Every catalog `translation()` finds joins one chain, in the order the languages were given. A
message the first catalog lacks is asked of the next, so a miss costs a probe per catalog.

```python
import gettext
import pathlib
import struct
import tempfile

def make_mo(messages):
    """Encode {msgid: msgstr} as a little-endian GNU .mo file."""
    entries = sorted({"": "Content-Type: text/plain; charset=UTF-8\n", **messages}.items())
    count = len(entries)
    tables, strings = [b"", b""], b""
    for column in (0, 1):
        for entry in entries:
            data = entry[column].encode()
            tables[column] += struct.pack("<2I", len(data), 28 + 16 * count + len(strings))
            strings += data + b"\0"
    header = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + 8 * count, 0, 0)
    return header + tables[0] + tables[1] + strings

with tempfile.TemporaryDirectory() as localedir:
    for language, messages in [("fi", {"Hello": "Hei"}), ("sv", {"Hello": "Hej", "Bye": "Hej då"})]:
        mofile = pathlib.Path(localedir, language, "LC_MESSAGES", "app.mo")
        mofile.parent.mkdir(parents=True)
        mofile.write_bytes(make_mo(messages))

    chain = gettext.translation("app", localedir, ["fi", "sv"])  # f = 2
    assert chain.gettext("Hello") == "Hei"  # O(k) - the first catalog has it
    assert chain.gettext("Bye") == "Hej då"  # O(f·k) - asked of the second
    assert chain.gettext("Thanks") == "Thanks"  # O(f·k) - nobody has it

    chain.add_fallback(gettext.NullTranslations())  # O(f) - appended at the end
```

## Common Patterns

### Installing `_` for a Whole Program

`install()` binds `_` in `builtins`, so every module can call it without importing anything. With
`fallback=True` behind it, a missing catalog is not an error: `_` returns messages unchanged.

```python
import builtins
import gettext

gettext.install("app", localedir="/nonexistent")  # O(d²) - no catalog, NullTranslations
assert builtins._("Hello") == "Hello"  # O(1)

gettext.NullTranslations().install(names=["ngettext"])  # O(1 + p)
assert builtins.ngettext("file", "files", 2) == "files"
```

### Choosing a Language per Request

A server answering in each user's language needs one catalog chain per language, not per request.
Build each once and keep it: every later request is a dictionary lookup.

```python
import gettext

catalogs = {}

def catalog_for(language):
    if language not in catalogs:  # O(1)
        catalogs[language] = gettext.translation(  # O(d² + b), once per language
            "app", "/nonexistent", [language], fallback=True
        )
    return catalogs[language]

assert catalog_for("fi") is catalog_for("fi")
assert catalog_for("fi").gettext("Hello") == "Hello"  # no catalog installed
```

## Performance Best Practices

✅ **Do**:

- Bind `translation(...).gettext` once and call that, so the file search runs once, not per message
- Keep one translation object per language when serving several, rather than calling
  `translation()` per request
- Build a `GNUTranslations` directly for a catalog that changes while the program runs;
  `translation()`'s cache never rereads a file

❌ **Avoid**:

- `gettext.gettext()` and its siblings in a hot loop - each call searches the locale directories
  again
- Long `languages` lists - every entry expands into several candidates, each an existence check
- Long fallback chains for messages that usually miss - every miss is asked of each catalog in turn

## Version Notes

- **Python 3.11+**: `lgettext()`, `ldgettext()`, `lngettext()`, `ldngettext()`,
  `bind_textdomain_codeset()`, `NullTranslations.output_charset()` and
  `NullTranslations.set_output_charset()` are removed, as is the `codeset` parameter of
  `translation()` and `install()`; `install()`'s `names` is keyword-only

## Related Modules

- **[locale](locale.md)** - the locale names `find()` expands, and the environment it reads
- **[builtins](builtins.md)** - where `install()` puts `_`
- **[struct](struct.md)** - the binary layout `GNUTranslations` unpacks
