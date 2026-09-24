# doctest Module Complexity

The `doctest` module finds interactive-session examples in docstrings and text files, runs them,
and compares what they print with what the text says they print. The work splits into three
stages: a finder walks a module and parses its docstrings, a runner executes each example and
checks its output, and the convenience functions (`testmod()`, `testfile()`, `DocTestSuite()`) wire
the two together.

Apart from the examples' own work, the cost that matters is the globals. Every docstring found
becomes a `DocTest` holding its own copy of the globals dictionary, so a finder's memory follows
docstrings times globals; and `testmod()` makes one for every function and class it walks, whether
it has a docstring or not.

`s` is the characters in the string being parsed, a docstring or a text file. `o` is the objects
the finder walks: the entries of the module's `__dict__` and `__test__` and of each class it
descends into. `t`
is the `DocTest` objects produced, `d` the total characters of their docstrings, and `g` the
entries in the globals dictionary each one copies - the module's `__dict__` by default, plus any
`extraglobs`. `c` is the classes that have a docstring, and `n` the lines of the module's source
file, each line priced at O(1) when it is scanned. `e` is the examples in one `DocTest`; `w` is
one example's text - its source and expected output - and `a` its actual output, both in
characters; and `x` is the examples' own work - running their code, plus `O(w + a)` each to check
and report what they printed, or difflib's cost instead when a `REPORT_*DIFF` flag diffs a failure. `r` is the distinct `DocTest` names a runner has run. Dictionary operations and
name comparisons are O(1).

## Complexity Reference

### Running Doctests

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.testmod(m=None, name=None, globs=None, verbose=None, report=True, optionflags=0, extraglobs=None, raise_on_error=False, exclude_empty=False)` | O(o + d + (t + 1)·g + t log t + n·(c + 1) + x) | O(o + d + (t + 1)·g + n + w + a) | `DocTestFinder.find()` then `run()` on each; `exclude_empty=False` makes t every function and class walked, docstring or not |
| `doctest.testfile(filename, module_relative=True, name=None, package=None, globs=None, verbose=None, report=True, optionflags=0, extraglobs=None, raise_on_error=False, parser=DocTestParser(), encoding=None)` | O(s + g + x) | O(s + g + w + a) | One `DocTest` for the whole file, so every example shares one namespace |
| `doctest.run_docstring_examples(f, globs, verbose=False, name='NoName', compileflags=None, optionflags=0)` | O(n + s + g + x) | O(n + s + g + w + a) | `f`'s own docstring only; does not recurse into members. The n is `f`'s source file, read to find the docstring's line |

### Unittest API

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.DocTestSuite(module=None, globs=None, extraglobs=None, test_finder=None, **options)` | O(o + d + (t + 1)·g + t log t + n·(c + 1)) | O(o + d + (t + 1)·g + n) | One test case per docstring that has examples; nothing runs until the suite does |
| Running one case of a `DocTestSuite` | O(e + g + x) | O(g + w + a) | Restores the `DocTest`'s globals from a saved copy afterwards |
| `doctest.DocFileSuite(*paths, module_relative=True, package=None, setUp=None, tearDown=None, globs=None, optionflags=0, parser=DocTestParser(), encoding=None)` | O(s + g) per file | O(s + g) per file | Reads and parses every file when the suite is built |
| `doctest.set_unittest_reportflags(flags)` | O(1) | O(1) | Returns the previous flags; raises `ValueError` for a flag that is not a reporting flag |

### DocTestFinder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.DocTestFinder(verbose=False, parser=DocTestParser(), recurse=True, exclude_empty=True)` | O(1) | O(1) | |
| `DocTestFinder.find(obj, name=None, module=None, globs=None, extraglobs=None)` | O(o + d + (t + 1)·g + t log t + n·(c + 1)) | O(o + d + (t + 1)·g + n) | Each class's line number is found by scanning the source from the top of the file, hence n·c; the t results are sorted by name |

### DocTestParser

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.DocTestParser()` | O(1) | O(1) | Holds no state between calls |
| `DocTestParser.parse(string, name='<string>')` | O(s) | O(s) | Alternating text and `Example` objects |
| `DocTestParser.get_examples(string, name='<string>')` | O(s) | O(s) | The `Example` objects only |
| `DocTestParser.get_doctest(string, globs, name, filename, lineno)` | O(s + g) | O(s + g) | Wraps the examples in a `DocTest`, which copies `globs` |

### DocTest and Example

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.DocTest(examples, globs, name, filename, lineno, docstring)` | O(g) | O(g) | Keeps the examples list it is given and a copy of `globs` |
| `DocTest.examples`, `DocTest.globs`, `DocTest.name`, `DocTest.filename`, `DocTest.lineno`, `DocTest.docstring` | O(1) | O(1) | `globs` is emptied by `run()` unless `clear_globs=False` |
| `doctest.Example(source, want, exc_msg=None, lineno=0, indent=0, options=None)` | O(1) | O(1) | Stores its arguments when each string already ends in a newline; adding a missing one copies that string, O(w) |
| `Example.source`, `Example.want`, `Example.exc_msg`, `Example.lineno`, `Example.indent`, `Example.options` | O(1) | O(1) | `options` maps flags set by a `# doctest:` directive to `True` or `False` |

### DocTestRunner

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.DocTestRunner(checker=None, verbose=None, optionflags=0)` | O(1) | O(1) | |
| `DocTestRunner.run(test, compileflags=None, out=None, clear_globs=True)` | O(e + g + x) | O(w + a) | For the largest single example: output is captured per example and discarded once it has been checked |
| `DocTestRunner.summarize(verbose=None)` | O(r log r) | O(r) | Sorts the names for the report |
| `DocTestRunner.report_start(out, test, example)` | O(1) | O(1) | Writes nothing unless verbose; verbose, it echoes the example's source and `want`, O(w) |
| `DocTestRunner.report_success(out, test, example, got)` | O(1) | O(1) | Writes `ok` when verbose, nothing otherwise |
| `DocTestRunner.report_failure(out, test, example, got)` | O(w + a) | O(w + a) | A header quoting the example's source, then `OutputChecker.output_difference()`, whose diff flags cost more |
| `DocTestRunner.report_unexpected_exception(out, test, example, exc_info)` | O(w + traceback) | O(w + traceback) | A header quoting the example's source, then the full traceback |
| `DocTestRunner.tries`, `DocTestRunner.failures`, `DocTestRunner.skips` | O(1) | O(1) | Running totals over every `run()`; `skips` is Python 3.13+ |
| `doctest.TestResults(failed, attempted, *, skipped=0)`, `TestResults.failed`, `TestResults.attempted`, `TestResults.skipped` | O(1) | O(1) | A named tuple of `(failed, attempted)`; `skipped` is Python 3.13+ |

### OutputChecker

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.OutputChecker()` | O(1) | O(1) | |
| `OutputChecker.check_output(want, got, optionflags)` | O(w + a) | O(w + a) | `NORMALIZE_WHITESPACE` and `ELLIPSIS` stay linear |
| `OutputChecker.output_difference(example, got, optionflags)` | O(w + a) | O(w + a) | Without a `REPORT_*DIFF` flag; with one, the cost is difflib's over the output lines, and `REPORT_NDIFF`, which also compares within lines, is the dearest on output with many changed lines |

### Debugging

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.DebugRunner(checker=None, verbose=None, optionflags=0)` | O(1) | O(1) | `run()` raises at the first failing example, leaving the globals intact |
| `doctest.DocTestFailure(test, example, got)`, `DocTestFailure.test`, `DocTestFailure.example`, `DocTestFailure.got` | O(1) | O(1) | Raised by `DebugRunner` for output that does not match |
| `doctest.UnexpectedException(test, example, exc_info)`, `UnexpectedException.test`, `UnexpectedException.example`, `UnexpectedException.exc_info` | O(1) | O(1) | Raised by `DebugRunner` for an exception the example did not expect |
| `doctest.script_from_examples(s)` | O(s) | O(s) | Examples become code; expected output and prose become comments |
| `doctest.testsource(module, name)` | O(o + d + (t + 1)·g + t log t + n·(c + 1)) | O(o + d + (t + 1)·g + n) | Runs a full `find()` over the module to pick out one docstring |
| `doctest.debug(module, name, pm=False)` | O(o + d + (t + 1)·g + t log t + n·(c + 1) + x) | O(o + d + (t + 1)·g + n) | `testsource()`, then `debug_script()` on the result; time in the debugger is not priced |
| `doctest.debug_src(src, pm=False, globs=None)`, `doctest.debug_script(src, pm=False, globs=None)` | O(s + g + x) | O(s + g) | Build or take the script and run it under `pdb`; with `pm=True`, run it plainly and open `pdb` only if it raises |

### Option flags

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `doctest.register_optionflag(name)` | O(1) | O(1) | Returns the existing flag for a name already registered |
| `doctest.DONT_ACCEPT_TRUE_FOR_1`, `doctest.DONT_ACCEPT_BLANKLINE`, `doctest.NORMALIZE_WHITESPACE`, `doctest.ELLIPSIS`, `doctest.IGNORE_EXCEPTION_DETAIL`, `doctest.SKIP` | O(1) | O(1) | Comparison flags; `SKIP` skips the example, and the rest change what matches, not the O(w + a) bound |
| `doctest.REPORT_UDIFF`, `doctest.REPORT_CDIFF`, `doctest.REPORT_NDIFF`, `doctest.REPORT_ONLY_FIRST_FAILURE`, `doctest.FAIL_FAST` | O(1) | O(1) | Reporting flags; only `FAIL_FAST` stops running examples |
| `doctest.COMPARISON_FLAGS`, `doctest.REPORTING_FLAGS` | O(1) | O(1) | The union of each group |

## Running Doctests

### Testing a Module

`testmod()` with no module tests `__main__`. It finds every docstring, gives each its own copy of
the module's globals, and runs them in name order.

```python
import doctest

def add(a, b):
    """
    >>> add(2, 3)
    5
    >>> add(-1, 1)
    0
    """
    return a + b

def greet(name):
    """
    >>> greet('Alice')
    'Hello, Alice!'
    """
    return f"Hello, {name}!"

results = doctest.testmod(report=False)  # O(o + d + t·g + ...) plus the examples
assert results.failed == 0
assert results.attempted == 3
```

### Each Docstring Gets Its Own Globals

A `DocTest` copies the globals it is given, so a name one docstring defines is not visible in the
next, and `run()` empties the copy afterwards. That isolation is what costs O(g) per docstring.

```python
import doctest

parser = doctest.DocTestParser()
shared = {'base': 10}

first = parser.get_doctest(">>> x = base + 1\n", shared, 'first', None, 0)  # O(s + g)
second = parser.get_doctest(">>> x\n11\n", shared, 'second', None, 0)
assert first.globs is not shared and first.globs == shared

runner = doctest.DocTestRunner(verbose=False)
assert runner.run(first, clear_globs=False).failed == 0
assert first.globs['x'] == 11
assert 'x' not in shared and 'x' not in second.globs

# The second docstring cannot see x, so its example fails
assert runner.run(second, out=lambda text: None).failed == 1

# run() clears the namespace it used unless told not to
assert runner.run(first).failed == 0  # O(e + g + x)
assert first.globs == {}
```

## The Cost of Finding Tests

### testmod() Copies Globals for Every Function

`DocTestFinder` skips objects with no docstring by default, but `testmod()` passes
`exclude_empty=False`: every function and class it walks becomes a `DocTest` with no examples and
its own O(g) copy of the globals. In a large module that is O(t·g) memory for nothing. Pass
`exclude_empty=True` when the undocumented names do not need to appear in the report.

```python
import doctest
import types

module = types.ModuleType('many')
for i in range(50):
    exec(f"def f{i}(): pass", module.__dict__)
exec("def documented():\n    '''\n    >>> 1 + 1\n    2\n    '''\n", module.__dict__)

all_found = doctest.DocTestFinder(exclude_empty=False).find(module)  # what testmod() does
with_examples = doctest.DocTestFinder().find(module)  # exclude_empty=True, the default

assert len(all_found) == 52  # every function, documented or not, and the module
assert len(with_examples) == 1
assert all(test.globs == module.__dict__ for test in all_found)  # each holds a copy
assert all(test.globs is not module.__dict__ for test in all_found)

results = doctest.testmod(module, report=False, exclude_empty=True)
assert results.failed == 0 and results.attempted == 1
```

### Class Line Numbers Scan the Source

The finder reports each docstring's line number. A function carries its own first line, but a
class does not, so the finder scans the module's source from the top for its `class` statement:
O(n) for each class with a docstring. A module with many documented classes in a long file pays
O(n·c) before any example runs.

```python
import doctest
import importlib.util
import pathlib
import sys
import tempfile

with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / 'shapes.py'
    path.write_text(
        "x = 1\n"
        "class Square:\n"
        "    '''\n"
        "    >>> Square().sides\n"
        "    4\n"
        "    '''\n"
        "    sides = 4\n"
    )
    spec = importlib.util.spec_from_file_location('shapes', path)
    shapes = importlib.util.module_from_spec(spec)
    sys.modules['shapes'] = shapes
    spec.loader.exec_module(shapes)

    [test] = doctest.DocTestFinder().find(shapes)  # O(n) for the one class
    assert test.name == 'shapes.Square'
    assert test.lineno == 2  # zero-based line of the docstring, found by scanning
    del sys.modules['shapes']
```

## Parsing Examples

`DocTestParser` runs in time linear in the string. `parse()` keeps the prose between examples,
`get_examples()` drops it, and `get_doctest()` wraps the examples with a copy of the globals.

```python
import doctest

text = """
Some prose.

>>> total = 0
>>> for n in range(3):
...     total += n
>>> total
3
"""

parser = doctest.DocTestParser()
pieces = parser.parse(text)  # O(s)
examples = parser.get_examples(text)  # O(s)
assert len(examples) == 3
assert [piece for piece in pieces if isinstance(piece, doctest.Example)] == examples
assert examples[1].source == 'for n in range(3):\n    total += n\n'
assert examples[2].want == '3\n'
assert examples[2].lineno == 6

example = doctest.Example('1 + 1', '2')  # O(1)
assert example.source == '1 + 1\n' and example.want == '2\n'
```

## Checking Output

### Comparison Flags

The comparison flags change what counts as a match. Each keeps the check linear in the two
outputs, so they are chosen for what they accept, not for speed. A flag can apply to a whole run
or, through a `# doctest:` directive, to one example.

```python
import doctest

checker = doctest.OutputChecker()

got = '[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]\n'
assert not checker.check_output('[0, 1, ..., 9]\n', got, 0)
assert checker.check_output('[0, 1, ..., 9]\n', got, doctest.ELLIPSIS)  # O(w + a)

assert checker.check_output('a   b\n', 'a b\n', doctest.NORMALIZE_WHITESPACE)
assert checker.check_output('1\n', 'True\n', 0)
assert not checker.check_output('1\n', 'True\n', doctest.DONT_ACCEPT_TRUE_FOR_1)

[example] = doctest.DocTestParser().get_examples(
    ">>> list(range(20))  # doctest: +ELLIPSIS\n[0, 1, ..., 19]\n"
)
assert example.options == {doctest.ELLIPSIS: True}
```

### Reporting a Failure

Without a diff flag a failure is reported as the expected output followed by the actual one,
O(w + a). The `REPORT_*DIFF` flags run difflib over the output lines instead. `REPORT_NDIFF`
also marks changes within each line, and on a failure with many changed lines it costs far more
than the other two.

```python
import doctest

checker = doctest.OutputChecker()
example = doctest.Example('f()', 'a\nb\nc\nd\n')
got = 'a\nB\nc\nd\n'

plain = checker.output_difference(example, got, 0)  # O(w + a)
assert plain.startswith('Expected:\n')

unified = checker.output_difference(example, got, doctest.REPORT_UDIFF)
assert unified.startswith('Differences (unified diff with -expected +actual):')
assert '    -b\n' in unified and '    +B\n' in unified
```

### Stopping at the First Failure

`REPORT_ONLY_FIRST_FAILURE` still runs every example and only stops reporting after the first
failure. `FAIL_FAST` stops running, so the examples after a failure cost nothing.
`DebugRunner` goes further and raises, leaving the globals in place for inspection.

```python
import doctest

text = ">>> 1\n2\n>>> calls.append(1)\n>>> calls.append(2)\n"
parser = doctest.DocTestParser()

def run(flags):
    calls = []
    test = parser.get_doctest(text, {'calls': calls}, 'demo', None, 0)
    doctest.DocTestRunner(optionflags=flags).run(test, out=lambda text: None)
    return calls

assert run(doctest.REPORT_ONLY_FIRST_FAILURE) == [1, 2]  # every example still runs
assert run(doctest.FAIL_FAST) == []  # stops after the failure

test = parser.get_doctest(text, {'calls': []}, 'demo', None, 0)
try:
    doctest.DebugRunner(verbose=False).run(test)
except doctest.DocTestFailure as failure:
    assert failure.got == '1\n'
    assert failure.example.want == '2\n'
    assert 'calls' in test.globs  # not cleared on failure
else:
    raise AssertionError('DebugRunner did not raise')
```

## Integrating with unittest

`DocTestSuite()` runs the finder once when it is built, with `exclude_empty=True`, and makes one
test case per docstring that has examples. Each case restores the `DocTest`'s globals from a saved
copy after it runs, so it can run again.

```python
import doctest
import types
import unittest

module = types.ModuleType('calc')
exec(
    "def double(x):\n"
    "    '''\n"
    "    >>> double(4)\n"
    "    8\n"
    "    '''\n"
    "    return 2 * x\n"
    "def undocumented():\n"
    "    pass\n",
    module.__dict__,
)
module.__file__ = 'calc.py'

suite = doctest.DocTestSuite(module)  # one find(); nothing runs yet
assert suite.countTestCases() == 1

result = unittest.TestResult()
suite.run(result)  # O(g + x) per case
assert result.wasSuccessful() and result.testsRun == 1

previous = doctest.set_unittest_reportflags(doctest.REPORT_NDIFF)  # O(1)
doctest.set_unittest_reportflags(previous)
```

## Testing a Text File

`testfile()` reads the whole file and parses it as one `DocTest`, so every example in the file
shares one namespace. `script_from_examples()` turns the same text into a script, which is what
the debugging helpers run under `pdb`.

```python
import doctest
import pathlib
import tempfile

text = """
Walk-through
============

>>> items = [3, 1, 2]
>>> sorted(items)
[1, 2, 3]
"""

with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / 'guide.txt'
    path.write_text(text)
    results = doctest.testfile(str(path), module_relative=False, report=False)  # O(s + g + x)

assert results.failed == 0 and results.attempted == 2

script = doctest.script_from_examples(text)  # O(s)
assert 'items = [3, 1, 2]' in script
assert '## [1, 2, 3]' in script
```

## Performance Best Practices

✅ **Do**:

- Pass `exclude_empty=True` to `testmod()` on a large module, so undocumented names do not each
  cost a copy of the globals
- Pass a small `globs` dictionary when the examples do not need the module's namespace; every
  docstring copies whatever it is given
- Use `FAIL_FAST` or `DebugRunner` when a failure makes the remaining examples pointless, since
  `REPORT_ONLY_FIRST_FAILURE` still runs them

❌ **Avoid**:

- `testsource()` or `debug()` in a loop over one module's names - each call walks the whole module
- `REPORT_NDIFF` on examples with long multi-line output; use `REPORT_UDIFF`

## Version Notes

- **Python 3.13+**: `TestResults.skipped` and `DocTestRunner.skips` count skipped examples, which
  `attempted` and `tries` now include; a `DocTestSuite` case whose examples are all skipped is
  reported as skipped

## Related Modules

- **[unittest](unittest.md)** - `DocTestSuite()` and `DocFileSuite()` produce its test suites
- **[difflib](difflib.md)** - the engine behind the `REPORT_*DIFF` flags
- **[pdb](pdb.md)** - the debugger `debug()` and `debug_src()` start
- **[inspect](inspect.md)** - how the finder decides which objects belong to a module
