# difflib Module Complexity

The `difflib` module compares sequences of hashable elements - usually the characters of a string
or the lines of a file - and renders the differences as opcodes, unified or context diffs, `ndiff`
deltas or HTML. Everything rests on `SequenceMatcher`, which indexes its second sequence once and
then searches the first for the longest matching blocks.

The cost of that search depends on the shape of the input far more than on its length. Identical
sequences of distinct elements, or sequences with nothing in common, are linear; changes at
regular intervals make it quadratic; an element repeated throughout both sequences can make it
cubic. `unified_diff()`, `context_diff()` and `ndiff()` are generators, but each runs the whole
match before it yields its first line.

`A` is the length of the first sequence `a` and `B` the length of the second sequence `b`, counted
in elements: characters for a string, lines for a list of lines. `k` is the matching blocks
`get_matching_blocks()` finds, its closing sentinel included; with `isjunk`, adjacent blocks it
found separately are merged before the list is returned, so the list can be shorter than k. `r`
is the lines in one replaced block of an `ndiff`, `s` is the characters in both inputs together,
`c` is the characters in one line, `p` is the possibilities given to `get_close_matches()`, `w` is
the length of its word and `q` the length of its longest possibility. Hashing and comparing one
element are treated as O(1); for lines that means the bounds count lines, not the characters
inside them.

## Complexity Reference

### SequenceMatcher

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `difflib.SequenceMatcher(isjunk=None, a='', b='', autojunk=True)` | O(B) | O(B) | Indexes `b` at once; `a` is only stored. `isjunk` runs once per distinct element of `b` |
| `SequenceMatcher.set_seqs(a, b)` | O(B) | O(B) | `set_seq1(a)` then `set_seq2(b)` |
| `SequenceMatcher.set_seq1(a)` | O(1) | O(1) | Keeps the index of `b`; only the cached results are dropped |
| `SequenceMatcher.set_seq2(b)` | O(B) | O(B) | Rebuilds the index; O(1) if `b` is the object already set |
| `SequenceMatcher.find_longest_match(alo=0, ahi=None, blo=0, bhi=None)` | O(A·B) worst | O(B) | Each position of `a` walks the index entries of its element in `b`; O(A) when no element of `b` repeats |
| `SequenceMatcher.get_matching_blocks()` | O(A + B) best, O(A·B·min(A, B)) worst | O(B) | One `find_longest_match` per block found; see [Input Shape Sets the Cost](#input-shape-sets-the-cost). Cached: later calls return the same list in O(1) |
| `SequenceMatcher.get_opcodes()` | As `get_matching_blocks()`, then O(k) | O(B) | Cached: later calls return the same list in O(1) |
| `SequenceMatcher.get_grouped_opcodes(n=3)` | As `get_opcodes()`, then O(k) | O(B) | A generator. Trims a leading and a trailing `equal` entry of the cached `get_opcodes()` list in place |
| `SequenceMatcher.ratio()` | As `get_matching_blocks()` | O(B) | O(k) once the blocks are cached |
| `SequenceMatcher.quick_ratio()` | O(A + B) | O(A + B) | An upper bound on `ratio()` from element counts; the count of `b` is cached, so a new `a` costs O(A) |
| `SequenceMatcher.real_quick_ratio()` | O(1) | O(1) | An upper bound on `quick_ratio()` from the two lengths |
| `SequenceMatcher.bjunk`, `SequenceMatcher.bpopular`, `SequenceMatcher.b2j` | O(1) | O(1) | The junk set, the popular set and the index of `b`, rebuilt by `set_seq2()` |

### Differ

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `difflib.Differ(linejunk=None, charjunk=None)` | O(1) | O(1) | Stores the two filters |
| `Differ.compare(a, b)` | As `get_matching_blocks()` on the lines, plus O(r) line pairs per replaced block | O(B + c) | A generator. Each line pair is a character-level `SequenceMatcher`, screened by the quick ratios first. 3.10–3.13 compare O(r²) to O(r³) pairs per block and hold O(r·c) |

### HtmlDiff

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `difflib.HtmlDiff(tabsize=8, wrapcolumn=None, linejunk=None, charjunk=IS_CHARACTER_JUNK)` | O(1) | O(1) | Stores the options |
| `HtmlDiff.make_table(fromlines, tolines, fromdesc='', todesc='', context=False, numlines=5)` | As `ndiff()`, plus O(s) | O(s) | Runs `ndiff()` over the lines, then builds the whole table as one string. The O(s) terms assume `wrapcolumn=None` |
| `HtmlDiff.make_file(fromlines, tolines, fromdesc='', todesc='', context=False, numlines=5, *, charset='utf-8')` | As `make_table()` | O(s) | `make_table()` wrapped in a complete HTML document |

### Diff functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `difflib.unified_diff(a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n')` | As `get_matching_blocks()` on the lines, plus O(A + B) | O(A + B) | A generator, but the first `next()` runs the whole match; the rest is output |
| `difflib.context_diff(a, b, fromfile='', tofile='', fromfiledate='', tofiledate='', n=3, lineterm='\n')` | As `unified_diff()` | O(A + B) | The same match, rendered in context format |
| `difflib.ndiff(a, b, linejunk=None, charjunk=IS_CHARACTER_JUNK)` | As `Differ.compare()` | O(B + c) | `Differ(linejunk, charjunk).compare(a, b)` |
| `difflib.diff_bytes(dfunc, a, b, fromfile=b'', tofile=b'', fromfiledate=b'', tofiledate=b'', n=3, lineterm=b'\n')` | As `dfunc`, plus O(s) | O(s) | Decodes every line of both inputs before `dfunc` starts, then encodes each output line |
| `difflib.restore(delta, which)` | O(1) per delta line | O(1) | A generator over an `ndiff()` or `Differ.compare()` delta |

### Close matches and helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `difflib.get_close_matches(word, possibilities, n=3, cutoff=0.6)` | O(w + p·q) screened, O(p·q·w·min(q, w)) worst | O(w + q + p) | Indexes `word` once. A possibility the quick ratios reject costs O(q); one they pass costs a full match. `n` is treated as a constant |
| `difflib.IS_LINE_JUNK(line)` | O(c) | O(c) | True for a blank line or one holding only `#` |
| `difflib.IS_CHARACTER_JUNK(ch)` | O(1) | O(1) | True for a space or a tab |
| `difflib.Match(a, b, size)`, `Match.a`, `Match.b`, `Match.size` | O(1) | O(1) | The named tuple `find_longest_match()` and `get_matching_blocks()` return |

## Sequence Matching

`SequenceMatcher` does its indexing when `b` is set and its searching when a result is first
asked for. The matching blocks, and the opcodes derived from them, are cached until either
sequence changes.

```python
from difflib import SequenceMatcher

matcher = SequenceMatcher(None, "abxcd", "abcd")  # O(B) - indexes "abcd"

blocks = matcher.get_matching_blocks()  # the full match, computed once
assert [tuple(block) for block in blocks] == [(0, 0, 2), (3, 2, 2), (5, 4, 0)]
assert matcher.get_matching_blocks() is blocks  # O(1) - cached

assert matcher.get_opcodes() == [
    ('equal', 0, 2, 0, 2),
    ('delete', 2, 3, 2, 2),
    ('equal', 3, 5, 2, 4),
]
assert round(matcher.ratio(), 3) == 0.889  # O(k) - reuses the cached blocks

longest = matcher.find_longest_match()  # O(A·B) worst
assert (longest.a, longest.b, longest.size) == (0, 0, 2)
```

### Input Shape Sets the Cost

`get_matching_blocks()` finds the longest matching block, then searches the ranges on either side
of it again. Each search walks the range of `a` it was given, so the total depends on how many
blocks there are and how they split the input:

- **Identical sequences of distinct elements with no junk, or sequences sharing no element**: one
  search, O(A + B).
- **No element repeats in `b`**: O(B + A·k) at worst. The bound is reached when the blocks are of
  similar length, as with a change every fifty lines, which is quadratic in the length of the
  files.
- **Elements repeated in both sequences**: a search walks every index entry of each element it
  meets, and the blocks can be found one at a time. That reaches O(A·B·min(A, B)), cubic, with
  the default `autojunk=True`.

```python
from difflib import SequenceMatcher

lines = [f"line {index}\n" for index in range(1_000)]

same = SequenceMatcher(None, lines, list(lines))
assert len(same.get_matching_blocks()) == 2  # one block and the sentinel - O(A + B)

edited = list(lines)
for index in range(25, 1_000, 50):
    edited[index] = "changed\n"
scattered = SequenceMatcher(None, lines, edited)
assert len(scattered.get_matching_blocks()) == 22  # k = 22 - O(B + A·k)
```

### The autojunk Heuristic

When `b` has at least 200 elements, any element occurring more than B/100 + 1 times is treated as
*popular* and left out of the index. That caps how many index entries one element can contribute,
but it does not change the growth class, and it changes the answer. On text over a small alphabet
every character is popular, and two strings that differ only in their first character can score
zero.

```python
import random
from difflib import SequenceMatcher

rng = random.Random(0)
text = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(1_000))

default = SequenceMatcher(None, "x" + text, "y" + text)  # autojunk=True
assert len(default.bpopular) == 26  # every letter is over 1% of b
assert default.ratio() == 0.0

exact = SequenceMatcher(None, "x" + text, "y" + text, autojunk=False)
assert exact.ratio() > 0.99  # every letter stays in the index
```

### Junk Filters

`isjunk` is called once per distinct element of `b`, when `b` is indexed, and the elements it
accepts are left out of the index.

```python
from difflib import IS_CHARACTER_JUNK, IS_LINE_JUNK, SequenceMatcher

calls = []

def is_space(element):
    calls.append(element)
    return element == " "

matcher = SequenceMatcher(is_space, " abcd", "abcd abcd")  # O(B)
assert sorted(calls) == [" ", "a", "b", "c", "d"]  # distinct elements, not positions
assert matcher.bjunk == {" "} and " " not in matcher.b2j

longest = matcher.find_longest_match()
assert (longest.a, longest.b, longest.size) == (1, 0, 4)  # " abcd" is not matched whole

assert IS_CHARACTER_JUNK(" ") and not IS_CHARACTER_JUNK("\n")  # O(1)
assert IS_LINE_JUNK("  # \n") and not IS_LINE_JUNK("x = 1\n")  # O(c)
```

### Comparing One Sequence Against Many

The index belongs to `b`. To compare one sequence against many, set it as `b` once and swap `a`
with `set_seq1()`, which is O(1); screen with the two quick ratios, which are upper bounds
on `ratio()`, before paying for a full match.

```python
from difflib import SequenceMatcher

matcher = SequenceMatcher()
matcher.set_seq2("difflib")  # O(B), once
index = matcher.b2j

scores = {}
for candidate in ["difflab", "diffuse", "zzz", "difflib"]:
    matcher.set_seq1(candidate)  # O(1) - the index of b is kept
    if matcher.real_quick_ratio() < 0.6:  # O(1)
        continue
    if matcher.quick_ratio() < 0.6:  # O(A + B) once, then O(A): b's counts are kept
        continue
    scores[candidate] = matcher.ratio()  # the full match, only for survivors

assert matcher.b2j is index
assert "zzz" not in scores
assert scores["difflib"] == 1.0
assert max(scores, key=scores.get) == "difflib"
```

## Line Diffs

### Unified and Context Diffs

Both functions build a `SequenceMatcher` over the lines and group its opcodes. They are
generators, but grouping needs the opcodes, so the first line costs the whole match and the rest
is output. From Python 3.14 they raise `TypeError` when `a` or `b` is a string rather than a list
of lines.

```python
from difflib import context_diff, unified_diff

old = "one\ntwo\nthree\nfour\n".splitlines(keepends=True)
new = "one\n2\nthree\nfour\nfive\n".splitlines(keepends=True)

diff = unified_diff(old, new, fromfile='old', tofile='new', n=1)  # nothing runs yet
assert next(diff) == '--- old\n'  # the whole match happens here
assert list(diff) == [
    '+++ new\n', '@@ -1,4 +1,5 @@\n',
    ' one\n', '-two\n', '+2\n', ' three\n', ' four\n', '+five\n',
]

context = list(context_diff(old, new, fromfile='old', tofile='new', n=1))
assert context[:4] == ['*** old\n', '--- new\n', '***************\n', '*** 1,4 ****\n']
assert '! two\n' in context and '! 2\n' in context
```

### ndiff and Differ

`ndiff()` matches lines the same way, then looks inside each replaced block for pairs of similar
lines to mark up character by character. Each pair is a character-level `SequenceMatcher`. From
Python 3.14 a line is compared only with lines at a similar offset in the block, O(r) pairs; on
3.10–3.13 every pair is compared at least once, and up to O(r³) pairs, holding O(r·c), when the
lines all resemble each other.

```python
from difflib import Differ, ndiff, restore

old = ["apple\n", "banana\n", "cherry\n"]
new = ["apple\n", "bananas\n", "cherry\n"]

delta = list(ndiff(old, new))
assert delta == ['  apple\n', '- banana\n', '+ bananas\n', '?       +\n', '  cherry\n']
assert list(Differ().compare(old, new)) == delta  # ndiff() also sets charjunk

assert list(restore(delta, 1)) == old  # O(1) per delta line
assert list(restore(delta, 2)) == new
```

### HTML Reports

`HtmlDiff` runs `ndiff()` and renders the result as one string, so it costs the delta plus the
characters of both inputs, and holds all of it.

```python
from difflib import HtmlDiff

old = ["line 1\n", "line 2\n", "line 3\n"]
new = ["line 1\n", "modified line 2\n", "line 3\n"]

html = HtmlDiff(wrapcolumn=40)
table = html.make_table(old, new, fromdesc='old', todesc='new')  # O(s) output
assert table.lstrip().startswith('<table')
assert 'modified' in table

page = html.make_file(old, new)  # the same table in a complete document
assert page.lstrip().startswith('<!DOCTYPE html') and page.rstrip().endswith('</html>')
```

### Bytes Input

`diff_bytes()` decodes every line of both inputs up front, runs a text diff function over them,
and encodes each line it yields, so bytes that are not valid text survive the round trip.

```python
from difflib import diff_bytes, unified_diff

old = [b"a\n", b"\xff\n"]
new = [b"a\n", b"b\n"]

diff = list(diff_bytes(unified_diff, old, new, b"old", b"new"))  # O(s) + the match
assert diff == [
    b'--- old\n', b'+++ new\n', b'@@ -1,2 +1,2 @@\n', b' a\n', b'-\xff\n', b'+b\n',
]
```

## Close Matches

`get_close_matches()` indexes the word once and screens each possibility with the two quick
ratios before running a full match, so a list of dissimilar possibilities costs little more than
reading it.

```python
from difflib import get_close_matches

possibilities = ["ape", "apple", "peach", "puppy"]

assert get_close_matches("appel", possibilities) == ['apple', 'ape']  # best first
assert get_close_matches("appel", possibilities, n=1) == ['apple']
assert get_close_matches("xyz", possibilities) == []  # rejected by the quick ratios

try:
    get_close_matches("appel", possibilities, n=0)
except ValueError as error:
    assert 'n must be > 0' in str(error)
else:
    raise AssertionError('n=0 was accepted')
```

## Common Patterns

### Ranking Near-Duplicates

```python
from difflib import SequenceMatcher

reference = "The quick brown fox jumps over the lazy dog"
candidates = [
    "The quick brown fox jumped over the lazy dog",
    "A slow green turtle",
    "The quick brown fox jumps over the lazy dog!",
]

matcher = SequenceMatcher(None, b=reference)  # index the shared sequence once - O(B)
ranked = []
for candidate in candidates:
    matcher.set_seq1(candidate)  # O(1)
    if matcher.quick_ratio() >= 0.8:  # O(A + B) screen
        ranked.append((matcher.ratio(), candidate))

ranked.sort(reverse=True)
assert [text for _, text in ranked] == [candidates[2], candidates[0]]
```

## Performance Best Practices

✅ **Do**:

- Put the sequence you compare against many others in `b` with `set_seq2()`, and swap the others
  in with `set_seq1()`, which keeps the index
- Screen with `real_quick_ratio()` and `quick_ratio()` before `ratio()` when only a threshold
  matters
- Pass `autojunk=False` when comparing characters of long text, or every character occurring more
  than B/100 + 1 times in `b` drops out of the index and `ratio()` can fall to zero
- Diff lines, not characters, for anything file-sized: there are far fewer of them, and distinct
  lines keep the match within O(B + A·k)

❌ **Avoid**:

- Assuming a diff of nearly identical inputs is linear: changes at regular intervals make it
  quadratic in their length
- One element repeated throughout both sequences, the shape that can make the match cubic
- `ndiff()` or `HtmlDiff` on large replaced blocks of similar lines before Python 3.14, where the
  intraline search is cubic in the block's lines

## Version Notes

- **Python 3.14+**: `Differ.compare()`, `ndiff()` and `HtmlDiff` compare each line in a replaced
  block only with lines at a similar offset: O(r) line pairs and O(c) space instead of up to
  O(r³) pairs and O(r·c)
- **Python 3.14+**: `unified_diff()` and `context_diff()` raise `TypeError` when `a` or `b` is a
  string instead of a list of lines
- **All Python 3**: `autojunk=True` is the default, so any `b` of 200 or more elements is subject
  to the popularity heuristic

## Related Modules

- **[filecmp](filecmp.md)** - compare files and directories for equality without computing a diff
- **[unittest](unittest.md)** - failed container assertions render their message with `ndiff()`
- **[doctest](doctest.md)** - the `REPORT_*DIFF` flags use this module's diff formats
