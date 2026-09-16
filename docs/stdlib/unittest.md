# unittest Module Complexity

The `unittest` package prices the work done *around* a test, never the test
itself. Finding test methods, ordering them, running fixtures, comparing two
values, recording an outcome and standing in for a dependency are the module's
own costs; what the test body does between them is the author's.

Four of those costs decide whether a large suite stays fast. A failed
comparison over a container costs far more than a passing one, because the
passing path stops at `==` while the failing path renders both operands and
diffs them. Class fixtures are driven by the order tests run in rather than by
how many classes there are, so interleaving two classes runs the first one's
`setUpClass` twice. Discovery descends into a subdirectory only when it is a
package, so a test file one level down from a plain directory is never found.
And a mock records every call on every ancestor
it hangs from, so both the time per call and the memory a long-lived mock holds
follow the depth of the attribute chain it was reached through.

## Complexity Reference

Size variables: n = tests in a suite or run; t = the cost of one test body and
its fixtures; a = names `dir()` reports on a class or module; m = test methods
matched on one class; f = tests that failed or errored; e = elements in a
sequence, set or mapping under comparison; L = characters in the two formatted
representations a failed comparison diffs; F = frames in a traceback, summed
over the chained exceptions behind it; r = log records captured; G = loggers
registered in the process; c = cleanup functions registered at one scope; g =
runs of consecutive tests sharing a class, in the order the suite executes; w =
files and directories discovery visits; M = modules in `sys.modules`; A = names
`dir()` reports on a mock's spec; q = keyword or named attributes an
operation is given; k = calls recorded on one mock; j = calls one
assertion expects; d = ancestors above a mock in its parent chain; C = children
a mock has already created, over the whole tree below it; D = entries in a
dictionary `patch.dict` patches, before and after the patch; S = names on an
autospec target that are functions.

Every assertion row below is the cost when the assertion *passes*. A failing
one adds the failure-message cost in the table after them, which is the larger
term for any comparison over a container.

### TestCase: construction and running

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase(methodName)` | O(1) | O(1) | Resolves the method to cache its docstring and builds a fresh six-entry type-dispatch dict per instance. A name the class does not define raises ValueError here rather than at run time, except for `runTest`, which may be absent |
| `TestCase.run(result)` | O(t + c) | O(1) + the result's | The skip flags, `setUp`, the body, `tearDown`, then the cleanups, each under its own context manager. Builds a `defaultTestResult()` when given none |
| `TestCase.debug()` | O(t + c) | O(1) | The same sequence with no result object, so an exception propagates to the caller. The first raising cleanup aborts the rest, which `run` does not |
| `TestCase.defaultTestResult()` | O(1) | O(1) | A fresh `TestResult` |
| `TestCase.countTestCases()` | O(1) | O(1) | Always 1 |
| `TestCase.setUp()`, `TestCase.tearDown()` | O(1) | O(1) | Empty by default; an override costs whatever it does, once per test |
| `TestCase.setUpClass()`, `TestCase.tearDownClass()` | O(1) | O(1) | Also empty by default. Run once per contiguous group of same-class tests, not once per class |
| `TestCase.subTest(msg, **params)` | O(p) + one `TestCase` | O(p) | p = parameters given plus those inherited from enclosing blocks, which stay visible in a nested block's failures. Each iteration constructs a whole subtest case, and the result is notified for passing subtests as well as failing ones |
| `TestCase.failureException` | O(1) | O(1) | The exception a failed assertion raises, `AssertionError` by default |

### TestCase: equality assertions

`assertEqual` dispatches on the operands' exact type. The dispatch table maps
`list`, `tuple`, `set`, `frozenset`, `dict` and `str` to the specific method
below, and requires `type(a) is type(b)`. Anything else, including a subclass
of those types and `OrderedDict`, falls back to plain `==` with no diff.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase.assertEqual(a, b)` | O(1) + the comparison | O(1) | One dict lookup on the exact type picks the function |
| `TestCase.assertNotEqual(a, b)` | cost of `!=` | O(1) | No dispatch; never uses a type-specific function |
| `TestCase.assertListEqual`, `TestCase.assertTupleEqual`, `TestCase.assertSequenceEqual` | O(e) | O(1) | Tries `==` first and returns on a match, so an equal pair never loops in Python. The element loop exists only to name the first difference |
| `TestCase.assertSetEqual(a, b)` | O(e) | O(e) | Two `difference` calls with no equality short-circuit, so equal sets still build both difference sets |
| `TestCase.assertDictEqual(a, b)` | O(e) | O(1) | `==` on two dicts |
| `TestCase.assertMultiLineEqual(a, b)` | O(length) | O(1) | `==` on two strings, linear in their characters rather than in e |
| `TestCase.assertCountEqual(a, b)` | O(e) hashable, O(e·D) otherwise | O(e) | D = distinct values among the elements. Counts both sequences into dictionaries when every element hashes, and falls back to a pairwise scan when any does not, marking each value's duplicates as it goes. Only the counting path has an equality short-circuit, so the fallback pays that scan even when the sequences are equal |
| `TestCase.assertAlmostEqual(a, b)` | O(1) | O(1) | Returns early on `==`, then `round(a - b, places)` against zero, or `abs(a - b) <= delta`. The two arguments are mutually exclusive |
| `TestCase.assertNotAlmostEqual(a, b)` | O(1) | O(1) | The same test negated, but it subtracts before comparing, so it needs `-` where `assertAlmostEqual` would have stopped at `==` |
| `TestCase.addTypeEqualityFunc(type, func)` | O(1) | O(1) | Adds an entry to that instance's dispatch dict, keyed by the exact type |

### TestCase: the remaining assertions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase.assertTrue(x)`, `TestCase.assertFalse(x)` | O(1) + `bool(x)` | O(1) | `bool` on a built-in container is O(1); on an object with `__len__` or `__bool__` it is whatever that costs |
| `TestCase.assertIs(a, b)`, `TestCase.assertIsNot(a, b)` | O(1) | O(1) | Identity, never `__eq__` |
| `TestCase.assertIsNone(x)`, `TestCase.assertIsNotNone(x)` | O(1) | O(1) | Identity against `None` |
| `TestCase.assertIn(a, b)`, `TestCase.assertNotIn(a, b)` | cost of `in` | O(1) | O(1) average for a set or dict, O(e) for a list, a tuple or a substring search |
| `TestCase.assertIsInstance(x, cls)`, `TestCase.assertNotIsInstance(x, cls)` | O(1) | O(1) | Linear in the class hierarchy, not in the data; an abstract base class adds its own subclass hook, which caches |
| `TestCase.assertIsSubclass(x, cls)`, `TestCase.assertNotIsSubclass(x, cls)` | O(1) | O(1) | Python 3.14+ |
| `TestCase.assertHasAttr(obj, name)`, `TestCase.assertNotHasAttr(obj, name)` | cost of `getattr` | O(1) | Python 3.14+; a property getter on the named attribute runs |
| `TestCase.assertGreater`, `TestCase.assertGreaterEqual`, `TestCase.assertLess`, `TestCase.assertLessEqual` | cost of the comparison | O(1) | One operator call |
| `TestCase.assertStartsWith`, `TestCase.assertEndsWith`, `TestCase.assertNotStartsWith`, `TestCase.assertNotEndsWith` | O(len(prefix)) | O(1) | Python 3.14+. The only assertions that cap the operand in their failure message at a fixed length rather than shortening it around the difference |
| `TestCase.assertRegex(text, regex)`, `TestCase.assertNotRegex(text, regex)` | cost of `search` | O(1) | A bare string is compiled first, and the `re` cache makes a repeated pattern a lookup. A backtracking pattern has no useful bound |
| `TestCase.fail(msg)` | O(1) | O(1) | Raises `failureException` unconditionally |
| `TestCase.skipTest(reason)` | O(1) | O(1) | Raises `SkipTest` from inside the test body |

### TestCase: context-manager assertions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase.assertRaises(exc)` | O(1) entering, O(F) exiting | O(1) | Entering installs nothing. Exiting clears every frame of the exception's own traceback, dropping the locals those frames held, and stores the exception without that traceback. A chained exception's traceback is left alone |
| `TestCase.assertRaisesRegex(exc, regex)` | O(F) + `search` | O(1) | As above, plus a search over `str(exception)` |
| `TestCase.assertWarns(cat)` | O(M + v) | O(M + v) | Entering snapshots `sys.modules` and clears the warning registry on *every* module in it, so the cost follows the import graph rather than the block. v = warnings the block raises, all of which are recorded |
| `TestCase.assertWarnsRegex(cat, regex)` | O(M + v) | O(M + v) | The same scan, then a search over each recorded warning until one matches |
| `TestCase.assertLogs(logger, level)` | O(G + r) | O(r) | Setting the logger's level invalidates every logger's level cache in the process, once on entry and again on exit. Each record is both stored and formatted as it arrives |
| `TestCase.assertNoLogs(logger, level)` | O(G + r) | O(r) | The same capture and the same two cache invalidations; it fails if anything was captured |
| `TestCase.output`, `TestCase.records` | O(1) | O(1) | Read on the watcher object `assertLogs` yields, not on the case: the formatted strings and the `LogRecord` objects it captured |

### TestCase: fixtures and cleanup

Cleanups run last-in first-out, and they run even when `setUp` raised, which
`tearDown` does not. A failing cleanup does not stop the others.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase.addCleanup(func, *args)` | O(1) | O(1) | Appends to a per-instance list |
| `TestCase.doCleanups()` | O(c) + the functions | O(1) | Pops the list to empty; each failure is reported and the rest still run |
| `TestCase.addClassCleanup(func, *args)` | O(1) | O(1) | Appends to a per-class list |
| `TestCase.doClassCleanups()` | O(c) + the functions | O(1), or O(c) failures | Run after `tearDownClass`. Unlike the other two scopes it keeps each failure, with its traceback, rather than re-raising one |
| `TestCase.enterContext(cm)` | cost of `__enter__` | O(1) | Python 3.11+; enters the manager and registers its `__exit__` as a cleanup |
| `TestCase.enterClassContext(cm)` | cost of `__enter__` | O(1) | Python 3.11+; the class-scoped form |
| `addModuleCleanup(func, *args)` | O(1) | O(1) | Module-scoped list, run after `tearDownModule` |
| `doModuleCleanups()` | O(c) + the functions | O(1), or O(c) failures | Python 3.11+ under this name. Same LIFO order. All run, and every failure is collected before the first of them is re-raised and the rest discarded |
| `enterModuleContext(cm)` | cost of `__enter__` | O(1) | Python 3.11+ |
| `setUpModule()`, `tearDownModule()` | O(1) | O(1) | Names a test module may define. The suite calls them on module transitions, on the same positional rule as the class fixtures |

### TestCase: identification and failure formatting

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestCase.id()` | O(1) | O(1) | The module, class and method name joined |
| `TestCase.shortDescription()` | O(s) | O(s) | s = characters in the method's docstring, which is split in full to keep its first line. `None` when there is none |
| `TestCase.longMessage` | O(1) | O(1) | True by default, so an explicit `msg` is appended to the standard explanation rather than replacing it. Setting it False does not stop the standard explanation being built |
| `TestCase.maxDiff` | O(1) | O(1) | Truncates a failure message after the diff has been built, so lowering it saves output but not work. `None` disables truncation |

A failure message is where a comparison's real cost is. Both operands are
rendered in full before anything is shortened.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| A failed `assertEqual` on two scalars, or any `assertIn`, `assertTrue` or comparison failure | O(R) | O(R) | R = characters in the operands' representations, computed whole and then shortened. A failure over a large container therefore renders that container |
| A failed `assertListEqual`, `assertTupleEqual`, `assertSequenceEqual` or `assertDictEqual` | O(L) or worse | O(L) | Both operands are pretty-printed, then diffed line by line. `difflib` sets the upper bound, and it is quadratic in the worst case. No size threshold skips this |
| A failed `assertMultiLineEqual` | O(L) or worse | O(L) | The same diff, but skipped in favour of a plain message once either string exceeds 65,536 characters. This is the only automatic diff guard |
| A failed `assertSetEqual` | O(e + R) | O(e + R) | Renders every element of both differences. It is the one comparison that never truncates, so `maxDiff` does not bound its message |
| A failed `assertCountEqual` | O(e) or O(e·D), plus O(R) | O(e + R) | The same counting or pairwise scan as the passing path, then one line per element whose counts differ, each carrying that element's representation |

### Skipping

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `skip(reason)`, `skipIf(cond, reason)`, `skipUnless(cond, reason)` | O(1) | O(1) | The condition is evaluated at import time, not test time, and sets an attribute on the method or class. The test is still loaded and instantiated; `run` sees the flag and records a skip without building an outcome or calling `setUp`. On a class the flag is inherited, so a subclass is skipped too |
| `expectedFailure(test)` | O(1) | O(1) | Marks the method; a failure is recorded as expected and a pass as an unexpected success |
| `SkipTest` | O(1) | O(1) | Raising it in a test, `setUp` or `setUpClass` skips; raised while a test module imports it skips the module |

### FunctionTestCase

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `FunctionTestCase(testFunc, setUp, tearDown, description)` | O(1) | O(1) | Wraps a plain function as a test. `id()` is the bare function name rather than the dotted form, and equality and hashing are over the four callables it was given |

### IsolatedAsyncioTestCase

Each test gets its own event loop, created before `asyncSetUp` and shut down
after the cleanups. The runner is built in debug mode, which makes every
coroutine created inside the test capture an origin traceback. Together these
are a fixed per-test cost far above a synchronous test's, and it does not
shrink with the test body.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `IsolatedAsyncioTestCase.run(result)` | loop setup + t + c + shutdown | O(1) | Builds a debug-mode runner and runs the coroutine on it. Shutdown then cancels whatever tasks are still pending, closes the async generators still open and drains the default executor, so a test that leaves work behind pays for it here |
| `IsolatedAsyncioTestCase.asyncSetUp()`, `IsolatedAsyncioTestCase.asyncTearDown()` | O(1) | O(1) | Empty by default; awaited around the test body, each on its own runner call |
| `IsolatedAsyncioTestCase.addAsyncCleanup(func, *args)` | O(1) | O(1) | Shares the one LIFO cleanup list with `addCleanup`, so sync and async cleanups unwind together |
| `IsolatedAsyncioTestCase.enterAsyncContext(cm)` | cost of `__aenter__` | O(1) | Python 3.11+ |
| `IsolatedAsyncioTestCase.loop_factory` | O(1) | O(1) | Python 3.13+; the callable the per-test runner builds its loop with. Setting it avoids touching the event loop policy, but not the per-test loop |

### TestSuite

A suite drops its reference to each test as soon as that test has run, so a
long run does not hold every case alive. `countTestCases()` still answers
correctly afterwards because the suite counts what it released. The cost is
that **a suite is single-use**: running it a second time raises `TypeError`.
Setting `_cleanup` to False keeps the tests at the price of holding them all.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestSuite(tests)` | O(n) | O(n) | Adds each item, rejecting a class rather than an instance |
| `TestSuite.addTest(test)` | O(1) | O(1) | Appends; the argument may be a `TestCase` or another suite |
| `TestSuite.addTests(tests)` | O(n) | O(n) | One `addTest` per item; a bare string is refused rather than iterated character by character |
| `TestSuite.countTestCases()` | O(N) | O(h) | N = nodes in the suite tree and h = its depth, since a nested suite recurses. The same sub-suite added twice counts twice |
| `TestSuite.run(result)` | O(n·t + g) | O(1) held by the suite | g = class transitions, each costing one `tearDownClass` and one `setUpClass`. The loop stops between tests when the result says so, which is how `failfast` and an interrupt take effect |
| `TestSuite.debug()` | O(n·t + g) | O(1) | The same sequence with fixtures but no result, so the first exception propagates |
| `TestSuite.__iter__()` | O(1) | O(1) | Returns an iterator over the top-level entries, so walking it costs O(n). It is not flattened, and it yields `None` for entries already run |

`BaseTestSuite` is the same container without class and module fixture
handling. It releases tests as it runs them exactly as `TestSuite` does, so it
is single-use on the same terms.

### TestLoader

`getTestCaseNames` scans everything `dir()` reports on the class, so a class
with many non-test attributes costs more to load than its test count suggests.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestLoader.getTestCaseNames(cls)` | O(a log a + m log m) | O(a) | `dir(cls)` sorts the class's whole namespace, which is the larger term. The survivors of the prefix and callability filter are then sorted again; since they arrive ordered the default comparator does linear work there, where one that disagrees with that order does not |
| `TestLoader.loadTestsFromTestCase(cls)` | O(a log a + m log m) | O(a + m) | One `TestCase` instance per name, built eagerly at load time. A class with no matching names yields one `runTest` case if the class defines one, and an empty suite otherwise |
| `TestLoader.loadTestsFromModule(module)` | O(a log a + Σ per class) | O(a + n) | Scans `dir(module)` for `TestCase` subclasses. A `load_tests` function in the module is handed the suite that scan built and replaces the *result*, so defining one does not save the scan. An exception from it becomes a synthetic failing test |
| `TestLoader.loadTestsFromName(name)` | O(imports + the object's load) | O(n) | Tries progressively shorter dotted prefixes until one imports. Every failed attempt formats a full traceback, including the ones a later success discards |
| `TestLoader.loadTestsFromNames(names)` | O(Σ over names) | O(n) | One `loadTestsFromName` per name, combined into a suite |
| `TestLoader.discover(start_dir, pattern)` | O(w log w per directory + imports) | O(n) | Sorts each directory's entries, matches each basename against `pattern`, and imports every file that matches. It descends into a subdirectory only when that subdirectory is a package, though the start directory itself need not be one. A package's `__init__.py` is imported whether or not its name matches the pattern. Importing is normally the larger term, though a tree of many unmatched files is all walk |
| `TestLoader.sortTestMethodsUsing` | O(1) | O(1) | The comparison behind the sort, a three-way compare of the names by default. `None` keeps `dir()` order |
| `TestLoader.testMethodPrefix` | O(1) | O(1) | `'test'` by default; the prefix test runs before any `getattr` |
| `TestLoader.testNamePatterns` | O(1) | O(1) | When set, each candidate's fully qualified name is matched against every pattern, so the filter costs the pattern count per name. An empty list matches nothing rather than everything |
| `TestLoader.errors` | O(1) | O(1) | Load-time errors collected so far. On the shared `defaultTestLoader` these accumulate across calls in one process |
| `defaultTestLoader` | O(1) | O(1) | The shared `TestLoader` instance `main` uses; its attributes are process-wide |

### TestResult

Failures are what a result's memory follows, because each one stores a
formatted traceback and keeps the test object alive. A passing test stores
nothing except its duration, which from Python 3.12 it always stores.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TestResult()` | O(1) | O(1) | Empty lists and counters |
| `TestResult.startTest(test)` | O(1) | O(1) | Increments `testsRun` and redirects stdout and stderr when `buffer` is set |
| `TestResult.stopTest(test)` | O(1), or O(o) after a failure | O(o) | Restores the streams; o = characters the test wrote, which are forwarded to the real ones only if it failed |
| `TestResult.startTestRun()`, `TestResult.stopTestRun()` | O(1) | O(1) | Hooks called once around the run |
| `TestResult.addSuccess(test)` | O(1) | O(1) | Does nothing |
| `TestResult.addError(test, err)`, `TestResult.addFailure(test, err)` | O(F + R) | O(R) | R = characters of the formatted text, which is produced now rather than held as frames, and covers the whole chained-exception graph plus each frame's source line. `tb_locals` adds a representation of every local in every frame |
| `TestResult.addSubTest(test, subtest, err)` | O(F + R) | O(R) | Successful subtests are notified but not stored; only a failing one appends, at the same formatting cost |
| `TestResult.addSkip(test, reason)`, `TestResult.addExpectedFailure(test, err)`, `TestResult.addUnexpectedSuccess(test)` | O(1) or O(F + R) | O(1) or O(R) | Appends the reason, the formatted traceback, or the test alone |
| `TestResult.addDuration(test, elapsed)` | O(1) | O(1) per test | Python 3.12+; appends the test's name and elapsed time for every test that was actually run, which is the one part of a result that grows with a fully passing run. A test skipped by its decorator or its class returns before the timer starts and gets no entry, where one that raises `SkipTest` from inside the body does |
| `TestResult.wasSuccessful()` | O(1) | O(1) | Three length checks. Skips and expected failures do not affect it |
| `TestResult.stop()`, `TestResult.shouldStop` | O(1) | O(1) | Sets and reads the flag the suite checks between tests, so stopping takes effect at the next test rather than mid-test |
| `TestResult.failfast` | O(1) | O(1) | When set, the first failure or error calls `stop()` |
| `TestResult.buffer` | O(1) | O(o) | o = characters the widest single test writes. One buffer pair is reused and truncated after each test, so the run's total output is not held |
| `TestResult.tb_locals` | O(1) | O(1) | Turns on local-variable rendering in every traceback formatted afterwards, so a recorded failure starts carrying the size of whatever its frames held |
| `TestResult.errors`, `TestResult.failures`, `TestResult.skipped`, `TestResult.expectedFailures`, `TestResult.unexpectedSuccesses` | O(1) | O(1) each | One entry per test that did not simply pass, so a wholly skipped run fills `skipped` with n of them. Each entry keeps its test object alive, and the two traceback collections keep that text as well |
| `TestResult.collectedDurations` | O(1) | O(n) | Python 3.12+; grows with every test that ran, not only with the failures |
| `TestResult.testsRun` | O(1) | O(1) | A counter |
| `TestResult.printErrors()` | O(1) | O(1) | A hook; the base class does nothing |

### TextTestResult and TextTestRunner

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `TextTestResult(stream, descriptions, verbosity)` | O(1) | O(1) | The reporting result `TextTestRunner` builds |
| `TextTestResult.getDescription(test)` | O(s) | O(s) | The test's `id()`, plus its docstring's first line when `descriptions` is on |
| `TextTestResult.printErrors()` | O(Σ traceback text) | O(1) | Writes each stored traceback once at the end of the run |
| `TextTestResult.printErrorList(flavour, errors)` | O(Σ traceback text) | O(1) | One flavour's share of the above |
| `TextTestResult.separator1`, `TextTestResult.separator2` | O(1) | O(1) | The rule strings between report sections |
| `TextTestRunner(stream, verbosity, failfast, buffer, resultclass, warnings, durations)` | O(1) | O(1) | Records the options; opens nothing |
| `TextTestRunner.run(suite)` | O(n·t + g + n log n) | O(n + f) | Installs one warnings filter for the whole run rather than per test. Reporting `--durations` sorts every collected duration before slicing, so that term follows the test count and not the number shown. At verbosity 1 or above the stream is flushed once per test |
| `TextTestRunner._makeResult()` | O(1) | O(1) | Instantiates `resultclass`; the hook a custom result is installed through |
| `TextTestRunner.resultclass` | O(1) | O(1) | `TextTestResult` unless replaced |

### main and TestProgram

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `main(module, argv, ...)` | O(parse + load + n·t) | O(n + f) | Constructing the program runs the tests. By default it then exits the process with the run's status; pass `exit=False` to get the object back instead |
| `TestProgram.parseArgs(argv)` | O(len(argv)) | O(1) | Builds three argument parsers on every call, which is the fixed startup cost of `main()` over driving a runner directly |
| `TestProgram.createTests()` | O(load) | O(n) | Either `loadTestsFromNames` over the named tests or a full `discover` |
| `TestProgram.runTests()` | O(n·t + reporting) | O(n + f) | Builds the runner and runs the suite |
| `TestProgram.module`, `TestProgram.progName` | O(1) | O(1) | The module under test and the name used in usage messages |

### Signal handling

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `installHandler()` | O(1) | O(1) | Replaces the interrupt handler once per process; a second call is a no-op |
| `registerResult(result)` | O(1) | O(1) | Adds the result to a weak-keyed map, so registering does not keep it alive |
| `removeResult(result)` | O(1) | O(1) | Discards it and reports whether it was there |
| `removeHandler(function)` | O(1) | O(1) | Restores the original handler, or wraps `function` so it runs with the handler removed |

An interrupt under the installed handler calls `stop()` on every registered
result, which is linear in the number registered - one per runner in the
process. A second interrupt raises instead of stopping.

### unittest.mock: Mock, MagicMock and the non-callable variants

Every mock instantiation builds a fresh class so that per-instance magic
methods cannot leak between mocks, and `MagicMock` then installs a descriptor
for each magic method on it. That makes `MagicMock` materially dearer than
`Mock` to construct, and both dearer than an ordinary object.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Mock(spec, side_effect, return_value, **kwargs)` | O(A) + `configure_mock` | O(A) + `configure_mock` | A = names on `spec`, read with `dir()` and checked one at a time for being coroutine functions. Keyword attributes are handed to `configure_mock` below, so a plain keyword builds no children while a dotted one creates every mock along its path. A list of strings is taken as the name set exactly as given, so it skips both the `dir()` call and the per-name inspection |
| `MagicMock(...)` | as `Mock` | as `Mock` | Installs a lazy descriptor per magic method on the new class, so the magic children themselves are built only when touched |
| `NonCallableMock(...)`, `NonCallableMagicMock(...)` | as above | as above | The same objects without `__call__`, so calling one raises |
| `AsyncMock(...)` | as `MagicMock` | as `MagicMock` | Also builds a stand-in code object of its own, so it costs a little more than `MagicMock` |
| `Mock.mock_add_spec(spec, spec_set)` | O(A) | O(A) | Replaces the name set wholesale rather than merging |
| `Mock.configure_mock(**kwargs)` | O(q log q + Σ depth) | O(q + Σ depth) | Sorts the keys by dot count so `a.b` is set after `a`, then walks each dotted name, building every mock along a path that does not exist yet. One deep keyword therefore costs more than its count suggests |
| `Mock.attach_mock(mock, attribute)` | O(d) | O(1) | Clears the given mock's name and parent so its calls start being recorded here, then walks this mock's ancestors to refuse a cycle. Assigning an already-named mock as a plain attribute does *not* wire it in, which is what this exists for |
| `Mock._get_child_mock(**kwargs)` | O(A) | O(1) | The hook that decides a child's class; override it to make children of a subclass. It scans the spec's coroutine names, so a large spec costs on every child creation |
| `Mock.__getattr__(name)` | O(1), or O(A) with a spec | O(1) amortized | The first access builds and caches a child mock; later accesses are a dict hit but still go through the lookup, so they are not as cheap as a real attribute. With a spec, each access also scans the name list |
| `Mock.return_value` | as a child access | O(1) | Reading it before any call creates the child that the call would return, at the same cost as reaching any other attribute for the first time |
| `Mock.side_effect` | O(1) | O(1) | A callable, an iterable or an exception; an iterable is wrapped once and advanced one item per call |
| `Mock.__dir__()` | O((A + i) log(A + i)) | O(A + i) | i = this mock's own children, not the whole tree below it. Merges the spec names, the type's names and those children, then sorts. `FILTER_DIR` is what hides the mock's own machinery |
| `FILTER_DIR` | O(1) | O(1) | Module flag, true by default |

### unittest.mock: recording and inspecting calls

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Calling a mock | O(d) appends, O(d²) name characters | O(d) records holding O(d²) characters | The call is appended to `mock_calls` on the mock and on every ancestor, under a name rebuilt by prefixing at each level, so the stored names lengthen with the distance as well. Nothing bounds the lists, so a mock called in a loop grows without limit until it is reset or dropped |
| `Mock.called`, `Mock.call_count` | O(1) | O(1) | A flag and a counter |
| `Mock.call_args` | O(1) | O(1) | The most recent call only |
| `Mock.call_args_list` | O(1) | O(k) | Every call to this mock, in order |
| `Mock.mock_calls` | O(1) | O(k) | Every call to this mock *and* to its descendants, which is why a parent's list is the longer one |
| `Mock.method_calls` | O(1) | O(k) | The subset made through an attribute rather than on the mock itself. Propagation stops at the first ancestor with no parent, where `mock_calls` continues to the root |
| `Mock.reset_mock(return_value, side_effect)` | O(C²) | O(C) | Replaces the call lists and recurses into every child and the return value. The already-visited check is a linear scan of a list, so resetting a wide mock tree is quadratic in its node count |
| `call(*args, **kwargs)` | O(1) | O(1) | The recorded-call value. Comparing two costs the arguments, plus their parent chains when both are chained calls |
| `call.call_list()` | O(d) | O(d) | Expands a chained call into the sequence of calls it represents, keeping only the levels that were actually called |

### unittest.mock: the assert methods

The counter checks read `call_count` and stop. Of the rest, `assert_called_with`
and its `_once` variant look at the most recent call alone, and the searching
ones rebuild the whole recorded list before scanning it, so their cost follows
how often the mock was called rather than how much you are asserting. With a
spec present, each rebuilt call is also re-bound through the target's
signature, which is the larger constant.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Mock.assert_called()`, `Mock.assert_not_called()`, `Mock.assert_called_once()` | O(1) | O(1) | Read `call_count`. Only the failure message is O(k) |
| `Mock.assert_called_with(*args, **kwargs)` | O(args) | O(1) | Compares `call_args` only, so it is unaffected by how many earlier calls there were |
| `Mock.assert_called_once_with(*args, **kwargs)` | O(args) | O(1) | The count check, then the same comparison |
| `Mock.assert_any_call(*args, **kwargs)` | O(k) | O(k) | Rebuilds the whole call list before scanning, so it costs the same whether the match is first or last |
| `Mock.assert_has_calls(calls, any_order)` | O(k·j) | O(k + j) | In order, it searches for the expected list as a contiguous run, copying a slice at each candidate position. With `any_order` it removes each expected call from a copy, which is a scan per expected call |

### unittest.mock: AsyncMock

An `AsyncMock` records calls when called and awaits when awaited, so an awaited
call is stored twice and a call that is never awaited advances only the first
set of counters.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `AsyncMock.await_count`, `AsyncMock.await_args` | O(1) | O(1) | The counter and the most recent await |
| `AsyncMock.await_args_list` | O(1) | O(k) | Every await, separate from `call_args_list` |
| `AsyncMock.assert_awaited()`, `AsyncMock.assert_awaited_once()`, `AsyncMock.assert_not_awaited()` | O(1) | O(1) | Counter checks |
| `AsyncMock.assert_awaited_with(...)`, `AsyncMock.assert_awaited_once_with(...)` | O(args) | O(1) | The last await only |
| `AsyncMock.assert_any_await(...)` | O(k) | O(k) | As `assert_any_call`, over awaits |
| `AsyncMock.assert_has_awaits(calls, any_order)` | O(k·j) | O(k + j) | As `assert_has_calls`, over awaits |
| `AsyncMock.reset_mock(...)` | O(C²) | O(C) | Also clears the await records |

### unittest.mock: ThreadingMock

`ThreadingMock` keeps one event per argument signature it has been asked about,
and finds it by scanning that list on every call. A mock called with a fresh
argument each time therefore costs quadratic total time, where one called
repeatedly with the same arguments does not. Waiting counts too: a wait for
arguments that never arrive registers a signature that every later call scans
past.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ThreadingMock(timeout, ...)` | as `MagicMock` | as `MagicMock` | Python 3.13+. The timeout every wait on this mock uses; left unset it is `None`, and a wait that is never satisfied blocks forever |
| Calling a `ThreadingMock` | the mock-call cost above, plus O(u) | O(d) records, plus O(u) events | u = argument signatures registered so far, which a wait adds to as well as a call. Each call takes a lock, scans for its signature, and sets both that event and the any-call event |
| `ThreadingMock.wait_until_called(timeout)` | O(1) + the wait | O(1) | Waits on the any-call event, which is never cleared, so after the first call it returns at once until the mock is reset |
| `ThreadingMock.wait_until_any_call_with(*args, **kwargs)` | O(u) + the wait | O(1) | Finds or creates that signature's event. It takes call arguments only, so a `timeout` keyword here joins the signature being waited for rather than bounding the wait. Waiting for arguments that never occur registers one anyway, lengthening every later call's scan |

### unittest.mock: patch

`patch` is a context manager, a decorator and a factory for the variants below.
As a decorator it enters and exits on *every* invocation of the decorated
function, so a test helper called in a loop pays for a new mock each time.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `patch(target, new)` entering | O(import + P) | O(A) | P = components in the dotted target, resolved on every entry rather than once at decoration. With no `new` it builds a `MagicMock`, which dominates; passing `new` explicitly skips that |
| `patch(...)` exiting | O(1) | O(1) | Puts the original back, or deletes the name when the attribute was inherited rather than local |
| `patch.object(target, attribute, new)` | O(1) + the mock | O(A) | No import and no dotted walk; otherwise identical |
| `patch.dict(in_dict, values, clear)` | O(D + q) | O(D) | Copies the whole dictionary on entry, applies the q supplied keys, then clears whatever it holds at exit and rebuilds it from the copy. The copy dominates, so the cost follows the target's size rather than the number of keys being changed, and a body that adds keys pays for those at exit too. Patching `sys.modules` this way is the expensive case |
| `patch.multiple(target, **kwargs)` | O(P·q) | O(q) | One patcher per named attribute, each resolving the target again |
| `patch.stopall()` | O(V²) | O(1) | V = patches started with `start()` and not yet stopped. Each stop removes itself from a shared list by scanning it |
| `patch.TEST_PREFIX` | O(1) | O(1) | `'test'`; which methods a class decorated with `patch` gets patched. Decorating a class costs one pass over `dir()` |

### unittest.mock: helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `create_autospec(spec, spec_set, instance)` | O(A + S) | O(A + S) | Reads and inspects all of `dir(spec)`, and for each of the S names that is a function builds a child mock and binds the original's signature to it. The remaining names become placeholders that recurse only when touched, which is why a class of data attributes costs far less than one of methods. Given a class rather than an instance it does the whole walk twice, once for the class and once for what calling it returns |
| `mock_open(mock, read_data)` | O(len(read_data)) | O(len(read_data)) | Builds one stream over `read_data` and configures a handle whose `read`, `readline`, `readlines` and iteration are served from it lazily; `readline` and iteration share a position. Every `open()` call rebuilds that stream at the same cost, and every call returns the same handle |
| `sentinel` | O(1) | O(1) | Each attribute access returns the same uniquely named object. The table is never pruned, so a distinct name is kept for the life of the process |
| `DEFAULT` | O(1) | O(1) | The sentinel a `side_effect` returns to mean "use `return_value` anyway" |
| `ANY` | O(1) | O(1) | Compares equal to everything, so it costs nothing and matches one argument. An operand whose own `__eq__` returns False rather than deferring only matches with `ANY` on the left, which is the order the call comparison uses |
| `seal(mock)` | O(Σ over C nodes of that node's `dir()`) | O(widest `dir()` + depth) | Walks the children already created and marks the tree, listing each node's names as it goes, so a later *new* attribute raises instead of springing into existence. Children created before the seal stay usable, and lazy autospec placeholders are not forced |
| `PropertyMock()` | one mock call per access | one call's records per access | A mock usable as a class attribute, so every access pays the per-call cost above: every read calls it and every assignment records a call with the value, so it is not free in a loop. It must be set on the class to act as a descriptor |

## A Failed Comparison Costs More Than a Passing One

`assertSequenceEqual` and its typed wrappers try `==` first and return on a
match, so a passing comparison over a list is one C-level scan. A failing one
formats both operands, splits them into lines and diffs the result. The diff
dominates, and `maxDiff` does not avoid it: the message is truncated after the
diff has been built. The plain failure messages work the same way, rendering an
operand in full before shortening the text.

```python
import unittest

case = unittest.TestCase()
left = [str(i) for i in range(2000)]
right = left[:-1] + ["different"]

case.assertListEqual(left, left)   # O(e), one == that succeeds

try:
    case.assertListEqual(left, right)  # O(L) to render, then the diff
except AssertionError as error:
    print(str(error).splitlines()[0])

case.maxDiff = 40  # shortens the message, not the work
try:
    case.assertListEqual(left, right)
except AssertionError as error:
    print("truncated:", "Diff is" in str(error))
```

The practical consequence is about loops, not about one assertion. An assertion
that fails once per run costs nothing worth measuring. An assertion over a
large container inside a `subTest` loop that fails on most iterations pays the
diff every time. `assertMultiLineEqual` is the only one that gives up on the
diff once its operands pass a size threshold.

## assertCountEqual Needs Hashable Elements

`assertCountEqual` ignores order. When every element hashes, it counts both
sequences into dictionaries and compares the counts. When any element does not
- a list of lists, a list of dicts - it falls back to a pairwise scan that has
no equality short-circuit, so it runs in full even when the two sequences are
equal and the assertion passes. The scan marks off each value's duplicates as it
goes, so its cost follows the distinct values rather than the length. Values
that are mostly distinct, which is the ordinary case, make that quadratic;
a handful of values repeated many times stays near linear.

```python
import unittest

case = unittest.TestCase()

hashable = [(i, i) for i in range(1000)]
case.assertCountEqual(hashable, list(reversed(hashable)))   # O(e)

unhashable = [[i] for i in range(1000)]
case.assertCountEqual(unhashable, list(reversed(unhashable)))  # O(e**2)
```

One unhashable element in either argument sends the whole comparison down that
scan, hashable elements beside it included. Converting the elements to tuples
before the assertion moves it back onto the counting path.

## Class Fixtures Follow Suite Order

`setUpClass` runs when the suite reaches a test whose class differs from the
previous test's, and `tearDownClass` when it leaves. The suite remembers only
the immediately preceding class, not the set of classes already prepared, so
two classes interleaved set up and tear down twice each. `setUpModule` and
`tearDownModule` follow the same positional rule at module granularity.

```python
import io
import unittest

order = []

class First(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        order.append("First.setUpClass")
    def test_a(self):
        pass
    def test_b(self):
        pass

class Second(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        order.append("Second.setUpClass")
    def test_a(self):
        pass

def run(tests):
    order.clear()
    suite = unittest.TestSuite(tests)  # a suite runs once; build a fresh one
    unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    return list(order)

print(run([First("test_a"), First("test_b"), Second("test_a")]))  # two calls
print(run([First("test_a"), Second("test_a"), First("test_b")]))  # three
```

Loading through `TestLoader` groups a class's methods together, so this bites a
suite assembled by hand or reordered by a plugin. Shuffling or sharding a suite
without keeping same-class tests adjacent multiplies the fixture cost, and
`unittest` offers no way to opt out of that beyond the ordering itself.

## Discovery Descends Only Into Packages

The start directory is read whatever it is, so a matching file sitting directly
in it is found. Going deeper is what needs a package: `discover` recurses into a
subdirectory only when that subdirectory holds an `__init__.py`, so a test file
one level down from a plain directory is never found, whatever the pattern says.
The reverse also holds: a package's `__init__.py` is imported during the walk
even though its name cannot match `test*.py`.

```python
import pathlib
import tempfile
import unittest

body = "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        pass\n"

with tempfile.TemporaryDirectory() as directory:
    root = pathlib.Path(directory)
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("")
    (root / "pkg" / "test_found.py").write_text(body)
    (root / "plain").mkdir()
    (root / "plain" / "test_missed.py").write_text(body)
    (root / "test_at_the_root.py").write_text(body)

    suite = unittest.TestLoader().discover(str(root))  # O(w log w) + imports
    # The package's file and the root's own file, but not the one under `plain`.
    print(suite.countTestCases())  # 2, not 3
```

A namespace package cannot be named as the discovery root before Python 3.14.
Through 3.13, passing one raises `TypeError`, because the loader asks the
imported module for a file it does not have.

## A Mock Call Is Recorded on Every Ancestor

A mock reached through an attribute chain keeps a reference to its parent, and
a call is appended to `mock_calls` on every mock above it as well as on itself.
The per-call cost therefore follows the depth of the chain, and so does the
memory each call consumes. The recorded name is rebuilt by prefixing at each
level, so the characters copied grow faster than the depth does.

```python
from unittest.mock import Mock

root = Mock()
root.service.client.session.get("/health")  # O(d) appends, d = 4 ancestors

print(root.mock_calls)                 # [call.service.client.session.get('/health')]
print(root.service.client.mock_calls)  # [call.session.get('/health')]
```

Nothing trims those lists. A mock standing in for something called in a tight
loop accumulates one entry per call on every ancestor, which is a leak for the
duration of the test unless `reset_mock()` is called - and resetting a wide tree
is itself quadratic in its node count. Attaching the mock at the shallowest
useful point keeps every one of those costs down.

## autospec Builds the Mock That spec Only Describes

`Mock(spec=target)` reads `dir(target)` once, checks each name for being a
coroutine function and keeps the list, so an unexpected attribute raises but
nothing is built. `create_autospec(target)` goes further: for each name that is
a function it builds a configured mock and binds the original's signature to it,
so calling a method with the wrong arguments raises too. Names that are not functions stay
placeholders until something touches them. Handed a class rather than an
instance it repeats the whole walk for what calling the class returns.

```python
from unittest.mock import Mock, create_autospec

class Service:
    def fetch(self, key, timeout=1.0):
        raise NotImplementedError

loose = Mock(spec=Service)      # O(A): the names, and no children
loose.fetch("k", "extra", "args", "accepted")

strict = create_autospec(Service)  # O(A + S): a mock per method, signatures bound
strict.fetch("k")
try:
    strict.fetch("k", "extra", "args", "rejected")
except TypeError as error:
    print(type(error).__name__)

names_only = Mock(spec=["fetch"])  # The names given, with no target to read
print(hasattr(names_only, "fetch"), hasattr(names_only, "store"))
```

The signature checking is what costs, and it is what you are paying for. Use
`spec` when the test only needs typo protection, `autospec` when a wrong call
should fail, and a list of strings when neither the real object's attributes nor
its signatures matter. A spec also changes the price of using the mock
afterwards: every attribute access checks the name list, and every call-list
assertion re-binds each recorded call through the signature.

## assertWarns Scans Every Loaded Module

Entering `assertWarns` clears the warning registry on every entry in
`sys.modules`, so that a warning already issued once is not suppressed. The cost
follows the size of the import graph rather than the block under test, so it is
paid in full by a block that raises one warning.
`assertRaises` does no such scan; its cost is on exit, where it clears the
frames of the exception's own traceback and so drops whatever those locals held.
A chained exception reached through `__cause__` or `__context__` keeps its
traceback, and with it those frames' locals.

```python
import unittest
import warnings

class Check(unittest.TestCase):
    def test_warning_is_raised(self):
        # Entering is O(M), M = len(sys.modules)
        with self.assertWarns(UserWarning):
            warnings.warn("deprecated", UserWarning)

        # Entering is O(1); exiting is O(F) in the traceback's frames
        with self.assertRaises(ValueError) as caught:
            int("not a number")
        print(caught.exception.__traceback__ is None)

suite = unittest.TestLoader().loadTestsFromTestCase(Check)
result = unittest.TextTestRunner(verbosity=0).run(suite)
assert result.wasSuccessful()
```

In a suite that asserts warnings in a loop this is measurable. Asserting once
per behaviour rather than once per case keeps it off the critical path.
`assertLogs` has a similar hidden term: setting the logger's level invalidates
every logger's level cache in the process, once on entry and once on exit.

## Related Documentation

- [Doctest Module](doctest.md) - The other test runner in the standard library
- [Difflib Module](difflib.md) - The diff behind every failed container comparison
- [Logging Module](logging.md) - What `assertLogs` captures, and whose caches it clears
- [Asyncio Module](asyncio.md) - The loop `IsolatedAsyncioTestCase` builds per test
- [Collections Module](collections.md) - The counter `assertCountEqual` uses when its elements hash
- [Inspect Module](inspect.md) - The signature binding `autospec` pays for
