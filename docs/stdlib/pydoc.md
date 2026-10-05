# pydoc Module Complexity

The `pydoc` module builds documentation from live objects: it imports what it is asked about,
walks the members with `inspect`, and renders their docstrings and signatures as text or HTML.
`help()`, `python -m pydoc` and the `pydoc -b` documentation server are all front ends to the same
renderers. Nothing rendered is cached: every call walks the object again.

`M` is the names in a module's namespace, `L` the names in its `__all__` and `C` the classes it
documents; `a` is the attributes a class has, inherited ones included, `d` the classes in its
method resolution order and `s` its direct subclasses; `w` is the characters of documentation
produced, counting the full `repr()` of any value that is built and then cut short. Rows write
**D** for the cost of documenting one object: O(M log M + C² + w) for a module, plus O(M·L) when
its `__all__` is a list or tuple, the class cost for each class it documents, and in HTML O(k²) for
the k submodules or package entries it lays out in columns; O(a log a + a·d² + w) for a class, plus
O(s log s) in text, which lists its built-in subclasses; O(w) for anything else. An
object without a docstring adds O(F) to read its source file into `linecache` once, where `F` is
the characters of that file, and on Python 3.10-3.12 a class without one adds O(F) every time.

`x` is the dotted parts of a name such as `json.decoder.JSONDecoder`; `N` is the files and
directories a scan of `sys.path` lists and `S` the characters of the modules' source; `t` is the
characters of the text an operation handles, whether a string argument or a docstring it reads;
`k` is the items of a list. Names, paths and URLs count as O(1) characters. A name given as a
string is imported first; the import system's own work, finding the module and running it, is not
counted in these bounds.

## Complexity Reference

### Rendering documentation

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.render_doc(thing, title='Python Library Documentation: %s', forceload=0, renderer=None)` | O(x² + D) | O(M + a + s + w) | Returns the page as a string; `renderer` defaults to `pydoc.text`, whose bold is backspace overstrike. An instance is documented through its class |
| `pydoc.doc(thing, title='Python Library Documentation: %s', forceload=0, output=None, is_cli=False)` | O(x² + D) | O(M + a + s + w) | `render_doc()` then the pager, or plain text to `output.write()` when `output` is given |
| `pydoc.help(request)` | O(x² + D) | O(M + a + s + w) | The module's `Helper` instance; see [Helper](#helper) for keywords, topics and `'modules'` |
| `pydoc.writedoc(thing, forceload=0)` | O(x² + D) | O(M + a + w) | HTML to `<name>.html` in the current directory |
| `pydoc.writedocs(dir, pkgpath='', done=None)` | O(D) per module | O(M + a + w) per module | `writedoc()` for every module under `dir`, which must be importable from `sys.path`; every package is imported to walk it, and every module stays imported |
| `pydoc.resolve(thing, forceload=0)` | O(x²) for a name, O(1) for an object | O(x) | Returns `(object, name)`; raises `ImportError` when a name finds nothing |
| `pydoc.locate(path, forceload=0)` | O(x²) | O(x) | Builds and imports each dotted prefix in turn until one is not a module, then follows attributes; `None` when nothing is found. `forceload` adds `safeimport()`'s scan of `sys.modules` for each prefix |
| `pydoc.describe(thing)` | O(1) | O(1) | A label such as `'package json'` or `'function dumps'` |

### Doc, TextDoc and HTMLDoc

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.text`, `pydoc.plaintext`, `pydoc.html` | O(1) | O(1) | The shared `TextDoc`, plain `TextDoc` and `HTMLDoc` instances |
| `pydoc.Doc`, `pydoc.TextDoc()`, `pydoc.HTMLDoc()` | O(1) | O(1) | Stateless; `Doc` is the base class |
| `Doc.document(object, name=None, *args)` | O(D) | O(M + a + s + w) | Dispatches to `docmodule`, `docclass`, `docroutine`, `docdata` or `docother` |
| `Doc.fail(object, name=None, *args)` | O(1) | O(1) | Raises `TypeError`; every `doc*` method of `Doc` itself is `fail` |
| `Doc.getdocloc(object, basedir=...)` | O(1) | O(1) | Where the reference for a recognised standard-library module lives, else `None`; `PYTHONDOCS` sets the base, a URL or a directory |
| `TextDoc.docmodule(object, name=None, mod=None, *ignored)`, `HTMLDoc.docmodule(object, name=None, mod=None, *ignored)` | O(D) | O(M + a + s + w) | Sorted members; a package also lists its directory, and in HTML that listing is O(k·w) for k entries |
| `TextDoc.docclass(object, name=None, mod=None, *ignored)`, `HTMLDoc.docclass(object, name=None, mod=None, funcs={}, classes={}, *ignored)` | O(a log a + a·d² + w), plus O(s log s) in text | O(a + s + w) | Each attribute is looked up on every class in the MRO to find the one that defines it |
| `TextDoc.docroutine(object, name=None, mod=None, cl=None, homecls=None)`, `HTMLDoc.docroutine(object, name=None, mod=None, funcs={}, classes={}, methods={}, cl=None, homecls=None)` | O(w) | O(w) | Signature and docstring |
| `TextDoc.docdata(object, name=None, mod=None, cl=None, *ignored)`, `HTMLDoc.docdata(object, name=None, mod=None, cl=None, *ignored)`, `TextDoc.docother(object, name=None, mod=None, parent=None, *ignored, maxlen=None, doc=None)`, `HTMLDoc.docother(object, name=None, mod=None, *ignored)` | O(w) | O(w) | A descriptor's docstring, or a value through the size-capped repr below |
| `TextDoc.bold(text)` | O(t) | O(t) | Three characters per character: `c`, a backspace, `c` |
| `plaintext.bold(text)` | O(1) | O(1) | Returns `text` unchanged |
| `TextDoc.indent(text, prefix='    ')`, `TextDoc.section(title, contents)` | O(t) | O(t) | |
| `TextDoc.formattree(tree, modname, parent=None, prefix='')`, `HTMLDoc.formattree(tree, modname, parent=None)` | O(k·w) | O(w) | k = classes in an `inspect.getclasstree()` result, w = the tree's text; a line is appended by copying the text so far, always in text and in HTML where a class's bases are listed. A flat tree is O(k²) |
| `TextDoc.formatvalue(object)`, `HTMLDoc.formatvalue(object)` | As `repr1` | As `repr1` | `'='` and a default value's capped repr |
| `HTMLDoc.page(title, contents)`, `HTMLDoc.heading(title, extras='')`, `HTMLDoc.section(title, cls, contents, ...)`, `HTMLDoc.bigsection(title, *args)` | O(t) | O(t) | Wrap markup already produced |
| `HTMLDoc.preformat(text)` | O(t) | O(t) | Escapes and keeps line breaks |
| `HTMLDoc.markup(text, escape=None, funcs={}, classes={}, methods={})` | O(t) | O(t) | One regex pass; links URLs, RFC and PEP numbers, and names found in the dicts |
| `HTMLDoc.multicolumn(list, format)` | O(k·w) | O(w) | Four columns; each item is appended by copying the table so far, so equal-width items cost O(k²) |
| `HTMLDoc.grey(text)`, `HTMLDoc.namelink(name, *dicts)`, `HTMLDoc.classlink(object, modname)`, `HTMLDoc.parentlink(object, modname)`, `HTMLDoc.modulelink(object)`, `HTMLDoc.modpkglink(modpkginfo)`, `HTMLDoc.filelink(url, path)` | O(1) | O(1) | One link or span each; `namelink` is O(1) per dict it tries |
| `HTMLDoc.index(dir, shadowed=None)` | O(e²) | O(e) | e = entries in `dir` and its subdirectories, listed to find packages; laid out by `multicolumn()`. The module index the server's front page shows |
| `HTMLDoc.repr(object)`, `HTMLDoc.escape(text)` | As `repr1`; O(t) | As `repr1`; O(t) | Bound from the class's `HTMLRepr` instance |

### TextRepr and HTMLRepr

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.TextRepr()`, `pydoc.HTMLRepr()` | O(1) | O(1) | [reprlib](reprlib.md) `Repr` subclasses; `HTMLRepr` escapes its output |
| `TextRepr.repr1(x, level)`, `HTMLRepr.repr1(x, level)` | As [reprlib](reprlib.md) for the types it handles; O(r) otherwise | O(r) | r = the length of `repr(x)`, which is built in full and then cut to `maxother` |
| `TextRepr.repr_string(x, level)`, `HTMLRepr.repr_string(x, level)` | O(1) | O(1) | Slices the head and tail before calling `repr()`, so a long string costs no more than a short one |
| `TextRepr.repr_instance(x, level)`, `HTMLRepr.repr_instance(x, level)` | O(r) | O(r) | Full `repr(x)`, then cut to `maxstring` |
| `HTMLRepr.escape(text)` | O(t) | O(t) | `&`, `<` and `>` |
| `TextRepr.maxlist`, `TextRepr.maxtuple`, `TextRepr.maxdict`, `TextRepr.maxstring`, `TextRepr.maxother`, and the same on `HTMLRepr` | O(1) | O(1) | 20, 20, 10, 100 and 100 |
| `TextRepr.maxarray`, `TextRepr.maxdeque`, `TextRepr.maxset`, `TextRepr.maxfrozenset`, `TextRepr.maxlong`, `TextRepr.maxlevel`, `TextRepr.fillvalue`, `TextRepr.indent`, and the same on `HTMLRepr` | O(1) | O(1) | Inherited unchanged from `reprlib.Repr` |

### Module and docstring helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.safeimport(path, forceload=0, cache={})` | O(1) once imported; O(len(sys.modules)) with `forceload` | O(1); O(q) with `forceload` | `None` when the module itself does not exist; `ErrorDuringImport` when it fails, or when a parent package is missing. `forceload` scans `sys.modules`, removes the module and its q submodules, keeping them alive in `cache`, and imports it again; a built-in module is not removed |
| `pydoc.importfile(path)` | O(1) plus the import | O(1) | Executes the file on every call and replaces its `sys.modules` entry |
| `pydoc.ErrorDuringImport(filename, exc_info)` | O(1) | O(1) | Python 3.12+ takes the exception; a `(type, value, traceback)` tuple is deprecated |
| `pydoc.getdoc(object)` | O(t) | O(t) | Without a docstring, falls back to the comments above the source: the file is read once into `linecache`, and on 3.10-3.12 a class also costs an O(F) parse of it on every call |
| `pydoc.splitdoc(doc)` | O(t) | O(t) | `(synopsis, rest)` when the second line is blank |
| `pydoc.synopsis(filename, cache={})` | O(h); O(1) cached | O(h) | h = characters read before it returns: through the module docstring, or to the first statement, or to the end of a file of comments. Cached per file until its modification time increases; a `.pyc` or extension file is imported instead |
| `pydoc.source_synopsis(file)` | O(h) | O(h) | Reads lines only as far as the docstring or the first statement; the rest of the file is not read |
| `pydoc.visiblename(name, all=None, obj=None)` | O(1); O(L) with a list or tuple `all` | O(1) | A name that reaches the export check is looked up with `name in all`; special names such as `__len__` are shown before it |
| `pydoc.classify_class_attrs(object)` | O(a·d²) | O(a) | `inspect.classify_class_attrs` with data descriptors and static methods relabelled |
| `pydoc.sort_attributes(attrs, object)` | O(f + k log k) | O(f + k) | In place, a namedtuple's f `_fields` first |
| `pydoc.allmethods(cl)` | O(a log a) per class on each path through `__bases__` | O(a·d) | Nothing is shared between paths, so a base inherited along two paths is walked twice |
| `pydoc.classname(object, modname)`, `pydoc.parentname(object, modname)` | O(1) | O(1) | `parentname` is Python 3.11.9+ and 3.12.3+ |
| `pydoc.isdata(object)` | O(1) | O(1) | Neither a module, class, routine, frame, traceback nor code object |
| `pydoc.replace(text, *pairs)` | O(t) per pair | O(t) | |
| `pydoc.cram(text, maxlen)` | O(maxlen) | O(maxlen) | Keeps the head and tail around `'...'` |
| `pydoc.stripid(text)` | O(t) | O(t) | Drops a trailing `' at 0x...'` from a repr |
| `pydoc.ispackage(path)` | O(1) | O(1) | Up to three stats; deprecated in Python 3.13 |
| `pydoc.ispath(x)` | O(t) | O(1) | Whether the string contains `os.sep` |
| `pydoc.pathdirs()` | O(P²) | O(P) | P = `sys.path` entries; at most one `isdir()` each, deduplicated through a list |

### Helper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.Helper(input=None, output=None)` | O(1) | O(1) | |
| `Helper.input`, `Helper.output` | O(1) | O(1) | The stream given, else `sys.stdin` or `sys.stdout` as they are at each use |
| `Helper.help(request, is_cli=False)` | O(x² + D) for an object or name | O(M + a + s + w) | `'keywords'`, `'symbols'`, `'topics'` and `'modules'` list; a keyword, symbol or topic shows its text; anything else goes to `doc()` |
| `Helper.showtopic(topic, more_xrefs='')`, `Helper.showsymbol(symbol)` | O(T) the first time, then O(z) | O(T), then O(z) | Imports [pydoc_data.topics](pydoc_data.md) on first use; T = all topic text, z = this topic's. Python 3.12.5+ writes to `output` when one was given, earlier releases to the pager |
| `Helper.listkeywords()`, `Helper.listsymbols()`, `Helper.listtopics()` | O(1) | O(1) | Fixed tables of under a hundred names each |
| `Helper.listmodules(key='')` | O(N log N) plus importing every package; as `apropos()` with `key` | O(N); O(N + y) with `key` | Sorts the top-level names into columns; with `key` it calls `apropos(key)`, which prints to `sys.stdout` rather than `output` |
| `Helper.list(items, columns=4, width=80)` | O(k log k) | O(k) | Sorted, then written in columns |
| `Helper.keywords`, `Helper.symbols`, `Helper.topics` | O(1) | O(1) | Class-level dicts mapping each name to the topic it shows |
| `Helper.intro()` | O(1) | O(1) | |
| `Helper.getline(prompt)` | O(t) | O(t) | `input()` when the input is `sys.stdin`, else `readline()` |
| `Helper.interact()` | O(t) per line, plus the request | O(t) | Until `q`, `quit` (`exit` from Python 3.13) or end of input. From Python 3.13.12 and 3.14.3, the end of an input stream other than `sys.stdin` does not stop it: it prompts again forever |

### ModuleScanner

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.ModuleScanner()` | O(1) | O(1) | |
| `ModuleScanner.run(callback, key=None, completer=None, onerror=None)` | O(N) plus importing every package; O(N + S) with `key` | O(N); O(N + y) with `key`, y = the largest source | Visits the built-in modules and every module on `sys.path`. With `key`, also imports every built-in module and reads each source module whole for its synopsis; setting `quit` on the scanner from the callback stops the `sys.path` walk, not the built-in loop before it |
| `pydoc.apropos(key)` | O(N + S) plus importing every package | O(N + y) | Prints each module whose name or synopsis contains `key`, ignoring case; every call reads the sources again |

### Pagers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.pager(text, title='')` | O(t) | O(t) | The first call replaces `pydoc.pager` with the pager `get_pager()` picks, which then serves the rest of the process; `title` is Python 3.13+ |
| `pydoc.get_pager()`, `pydoc.getpager()` | O(1) | O(1) | `plain_pager` unless stdin and stdout are terminals; on a terminal it may run shell commands to find `less` or `more` |
| `pydoc.plain(text)` | O(t) | O(t) | Strips backspace overstrike |
| `pydoc.plain_pager(text, title='')`, `pydoc.plainpager(text)` | O(t) | O(t) | Writes the plain text to `sys.stdout` |
| `pydoc.pipe_pager(text, cmd, title='')`, `pydoc.pipepager(text, cmd)` | O(t) | O(t) | Pipes to a shell command and waits for it to exit |
| `pydoc.tempfile_pager(text, cmd, title='')`, `pydoc.tempfilepager(text, cmd)` | O(t) | O(t) | Writes a temporary file and runs `cmd` on it |
| `pydoc.tty_pager(text, title='')`, `pydoc.ttypager(text)` | O(t) for the first screen, then O(n) per key | O(t) | n = lines; pages a screenful at a time on the terminal |

### Server and command line

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pydoc.browse(port=0, *, open_browser=True, hostname='localhost')` | O(1) to start | O(1) | One thread serving one request at a time, until `q` at the `server>` prompt. Every page is rendered when it is requested, and a module page imports its module again |
| `pydoc.cli()` | Cost of the option used | Cost of the option used | Reads `sys.argv`, and adds the current directory to the front of `sys.path` when it is missing |
| `python -m pydoc <name>` | O(x² + D) | O(M + a + s + w) | `help(name)`; a name containing `os.sep` is a file, imported with `importfile()` |
| `python -m pydoc -k <key>` | O(N + S) plus importing every package | O(N + y) | `apropos(key)` |
| `python -m pydoc -w <name>` | O(x² + D), or O(D) per module for a directory | O(M + a + w) | `writedoc()`, or `writedocs()` for a directory |
| `python -m pydoc -p <port>`, `-n <hostname>`, `-b` | O(1) to start | O(1) | `browse()`; `-b` opens a web browser |

## Rendering Documentation

### Text, Plain Text and HTML

`render_doc()` returns the page `help()` would show. The default text renderer bolds headings by
overstriking each character with a backspace, which a pager turns into bold; `pydoc.plaintext`
leaves it out, and `doc(..., output=stream)` uses it to write to a stream without a pager.

```python
import io
import json
import pydoc

text = pydoc.render_doc(json.dumps, renderer=pydoc.plaintext)  # O(w)
assert text.startswith('Python Library Documentation: function dumps in module json')

# The default renderer overstrikes: each character, a backspace, the character again
assert 'd\bdu\bum\bmp\bps\bs' in pydoc.render_doc(json.dumps)
assert pydoc.plain(pydoc.render_doc(json.dumps)) == text  # O(t)

buffer = io.StringIO()
pydoc.doc(len, output=buffer)  # O(w) - plain text to the stream, no pager
assert buffer.getvalue().startswith('Python Library Documentation: built-in function len')

page = pydoc.html.page(pydoc.describe(json), pydoc.html.document(json))  # O(D)
assert page.startswith('<!DOCTYPE html')
assert '<title>Python: package json</title>' in page
```

### Naming an Object Imports It

Given a string, `pydoc` imports each dotted prefix that is a module and follows attributes for the
rest. The import runs the module's code the first time; later calls find it in `sys.modules`.
`forceload=1` takes a module other than a built-in one out of `sys.modules` and runs it again.

```python
import json.decoder
import pathlib
import pydoc
import sys
import tempfile

assert pydoc.locate('json.decoder.JSONDecoder.decode') is json.decoder.JSONDecoder.decode  # O(x)
assert pydoc.locate('json.no_such_name') is None

try:
    pydoc.resolve('no_such_module_anywhere')
except ImportError as error:
    assert 'No Python documentation found' in str(error)
else:
    raise AssertionError('an unknown name was resolved')

with tempfile.TemporaryDirectory() as directory:
    log = pathlib.Path(directory, 'runs.log')
    pathlib.Path(directory, 'noisy.py').write_text(
        f'"""Logs every run."""\nwith open({str(log)!r}, "a") as f:\n    f.write("run\\n")\n'
    )
    sys.path.insert(0, directory)
    try:
        pydoc.render_doc('noisy')  # imports noisy, which runs its code
        pydoc.render_doc('noisy')  # found in sys.modules
        assert log.read_text().count('run') == 1

        pydoc.render_doc('noisy', forceload=1)  # removed from sys.modules and run again
        assert log.read_text().count('run') == 2
    finally:
        sys.path.remove(directory)
        del sys.modules['noisy']
```

### What a Render Costs

A module's members are listed with `inspect.getmembers()`, which sorts them, and each visible one is
rendered. Two things add to that. When the module has an `__all__` list or tuple, every member is
looked up in it with `in` when its name reaches that check, so the check alone is O(M·L). Each of a class's attributes is looked up
on every class in its MRO to find the one that defines it, and a lookup the interpreter's type cache
misses walks that class's MRO in turn, so a deep hierarchy costs O(a·d²) even when it defines
little.

On Python 3.10-3.12, a class without a docstring costs more than one with: `getdoc()` falls back to
the comments above the class, and finding the class in its source parses the whole file. A module
of `C` classes without docstrings then spends O(C·F) on parsing alone. Python 3.13 locates the class from the line
number it records.

```python
import pydoc

class Base:
    def method(self):
        """Documented once, here."""

class Deep(Base):
    pass

for level in range(10):
    Deep = type(f'Level{level}', (Deep,), {})

text = pydoc.render_doc(Deep, renderer=pydoc.plaintext)  # O(a·d² + w)
assert 'Method resolution order:' in text
assert 'Methods inherited from Base:' in text
assert pydoc.visiblename('method', all=['other', 'method'])  # O(L) - a list is searched
assert not pydoc.visiblename('_private')
```

## Writing HTML Files

`writedoc()` renders one object to `<name>.html` in the current directory. `writedocs()` does that
for every module under a directory, importing each package to find its submodules and each module
to document it. The modules must be importable by their names from `sys.path`.

```python
import contextlib
import io
import os
import pathlib
import pydoc
import sys
import tempfile

with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as target:
    package = pathlib.Path(source, 'shapes')
    package.mkdir()
    (package / '__init__.py').write_text('"""Shapes."""\n')
    (package / 'circle.py').write_text('"""Circles."""\ndef area(r):\n    return 3.14159 * r * r\n')

    sys.path.insert(0, source)
    previous = os.getcwd()
    os.chdir(target)
    report = io.StringIO()
    try:
        with contextlib.redirect_stdout(report):
            pydoc.writedocs(source)  # O(D) per module, each imported
    finally:
        os.chdir(previous)
        sys.path.remove(source)

    assert sorted(os.listdir(target)) == ['shapes.circle.html', 'shapes.html']
    assert 'wrote shapes.circle.html' in report.getvalue()
```

## Searching Modules

`apropos()`, `python -m pydoc -k` and `help('modules spam')` visit every module on `sys.path`.
Packages are imported to find their submodules, so their code runs, and each source module is read
whole to take the first line of its docstring; every built-in module is imported too. Every
search reads the sources again. `help('modules')` without a key lists names only, but it imports
every package just the same.

`synopsis()` reads a single file only as far as its docstring, and caches the answer until the
file's modification time increases.

```python
import pathlib
import pydoc
import sys
import tempfile

with tempfile.TemporaryDirectory() as directory:
    geometry = pathlib.Path(directory, 'geometry.py')
    geometry.write_text('"""Area and perimeter helpers."""\n' + 'x = 1\n' * 1000)
    assert pydoc.synopsis(str(geometry)) == 'Area and perimeter helpers.'  # O(h)
    assert pydoc.synopsis(str(geometry)) == 'Area and perimeter helpers.'  # O(1) - cached

    kit = pathlib.Path(directory, 'kit')
    kit.mkdir()
    (kit / '__init__.py').write_text('"""A kit."""\n')
    (kit / 'tools.py').write_text('"""Tools."""\n')

    found = []
    saved = sys.path[:]
    sys.path[:] = [directory]  # scan only this directory
    try:
        pydoc.ModuleScanner().run(lambda path, name, synopsis: found.append(name))  # O(N)
    finally:
        sys.path[:] = saved

    assert {'geometry', 'kit', 'kit.tools'} <= set(found)
    assert 'kit' in sys.modules  # imported to look inside it
    assert 'kit.tools' not in sys.modules  # a module is only listed
    del sys.modules['kit']
```

## The Interactive Helper

`help()` at the prompt is a `Helper` reading `sys.stdin`. Give it streams and it answers without a
terminal: object and module help, and the keyword, symbol and topic lists, go to `output`.
Keyword and topic texts come from [pydoc_data](pydoc_data.md), imported the first time one is
shown; they reach `output` from Python 3.12.5, and the pager before that. End a scripted session
with `q`: from Python 3.13.12 and 3.14.3, reaching the end of the input stream does not stop it.

```python
import io
import pydoc

output = io.StringIO()
helper = pydoc.Helper(input=io.StringIO('keywords\nlen\nq\n'), output=output)

helper.interact()  # one request per line, until q - O(t) per line, plus the request
answer = output.getvalue()
assert 'nonlocal' in answer  # from the fixed keyword table
assert 'Help on built-in function len in module builtins' in answer
```

## Pagers

The first call to `pydoc.pager()` picks a pager and puts it in `pydoc.pager`'s place, so the
choice is made once per process. When standard input or output is not a terminal it is the plain
pager, which writes the text without overstrike to `sys.stdout`. On a terminal, `MANPAGER` or
`PAGER` names a command; otherwise `pydoc` runs shell commands to look for one such as `less`.

```python
import contextlib
import io
import pydoc

captured = io.StringIO()
with contextlib.redirect_stdout(captured):  # not a terminal, so the plain pager
    pydoc.pager('b\bbold, then plain\n')  # O(t)

assert captured.getvalue() == 'bold, then plain\n'
assert pydoc.pager is pydoc.plainpager  # chosen once and kept
```

## The Documentation Server

The server renders each page when it is requested, with the HTML renderer, and handles one request
at a time. A module page imports the module again on every request, as `forceload=1` does, so edits
to the source show up on reload. The search box runs the same scan as `apropos()`.

```bash
# Serve on a free port; type q at the server> prompt to stop
python -m pydoc -p 0
```

`python -m pydoc -b` starts the same server and opens a web browser on it.

## Common Patterns

### Documenting a File by Path

`python -m pydoc ./script.py` imports the file by path and documents it. The import runs the file,
every time.

```python
import pathlib
import pydoc
import sys
import tempfile

with tempfile.TemporaryDirectory() as directory:
    script = pathlib.Path(directory, 'tool.py')
    script.write_text('"""A small tool."""\ndef run(path):\n    """Process path."""\n')

    module = pydoc.importfile(str(script))  # runs the file
    try:
        text = pydoc.render_doc(module, renderer=pydoc.plaintext)  # O(D)
    finally:
        del sys.modules['tool']

assert 'tool - A small tool.' in text
assert 'run(path)' in text
```

## Performance Best Practices

✅ **Do**:

- Pass the object rather than its name when you have it: no import, and `resolve()` is O(1)
- Use `renderer=pydoc.plaintext` or `doc(..., output=stream)` for text you will process; it never
  starts a pager
- Search with `-k` once and keep the result; every search reads all the source on `sys.path` again
- Give classes docstrings in a large module that has to be documented on Python 3.10-3.12

❌ **Avoid**:

- Running `pydoc`, `help('modules')` or `-k` where importing an untrusted package would be unsafe:
  documenting runs the code it documents
- `forceload=1` without a changed source: it runs the module again and drops its submodules from
  `sys.modules`
- Setting `PAGER` after the first `help()` in a process and expecting it to apply

## Version Notes

- **Python 3.11+**: `writedoc()` raises `ImportError` for a name it cannot find, and `doc()` writes
  that message to `output` when one is given; Python 3.10 prints both
- **Python 3.12.5+**: `Helper` writes keyword, symbol and topic texts to the `output` it was given
  instead of the pager
- **Python 3.13+**: Documenting a class without a docstring no longer parses its source file
- **Python 3.13+**: The pager chooser is `get_pager()` and the pagers are `plain_pager()`,
  `pipe_pager()`, `tempfile_pager()` and `tty_pager()`, which take a `title`; `getpager()`,
  `plainpager()`, `pipepager()`, `tempfilepager()` and `ttypager()` remain as aliases
- **Python 3.13.12+, 3.14.3+**: `Helper.interact()` reading a stream other than `sys.stdin` no longer
  returns at the end of it, so a scripted session must end with `q`

## Related Modules

- **[inspect](inspect.md)** - The member, signature and source lookups every render is built on
- **[pydoc_data](pydoc_data.md)** - The keyword and topic texts `help()` shows
- **[reprlib](reprlib.md)** - The size-capped repr used for values and defaults
- **[pkgutil](pkgutil.md)** - The module walk behind searches and `writedocs()`
- **[doctest](doctest.md)** - Runs the examples in the docstrings `pydoc` displays
