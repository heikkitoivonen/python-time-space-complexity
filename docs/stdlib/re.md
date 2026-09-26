# re Module Complexity

The `re` module compiles a regular expression into a program for a backtracking matcher written
in C. Compiling is paid once per pattern; matching costs the subject's length, multiplied by
however much the pattern makes the matcher retry.

A match records positions into the subject rather than copying text out of it. Text is copied
only when you ask for it - `group()`, `findall()`, `sub()` - so the size of a result is the
text it hands back, not the subject it came from.

`n` is the characters in the pattern (or in the string given to `escape()`), `m` the
characters in the subject, `k` the matches found, `c` the capturing groups in the pattern, `g`
the characters a result copies out of the subject, `t` the characters in a replacement template,
`r` the characters in the result of `sub()`, and `f` the cost of one call to a replacement
function. Matching bounds hold the pattern fixed: they are in m, not n. They assume one attempt
at one position costs O(m), which holds when the pattern can match a stretch of text in only one
way, as `\d+` and `\w+@` can. Where it can match the same characters in several ways - nested or
adjacent repetitions such as `(a+)+b` and `a*a*b`, or overlapping alternatives inside a
repetition such as `(?:a|aa)+b` - a failing attempt can be polynomial or exponential in m (see
[Catastrophic Backtracking](#catastrophic-backtracking)).

`s` is the total cost of the attempts a scan makes. `search()` and the calls built on it may
retry at each start position, so s is O(m) when each attempt examines a bounded stretch of the
subject, and O(m²) when attempts run on to the end of it (see
[One Attempt or Many](#one-attempt-or-many)). Space columns count what a call allocates, its
result included; freeing an object is charged to whatever built it. The backtracking stack
comes on top: O(1) for a single-character repeat such as `[ab]*`, O(m) for a repeated group
such as `(?:ab)*`, which records each iteration.

## Complexity Reference

### Pattern

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.compile(pattern, flags=0)` | O(n) | O(n) | O(n²) when the alternatives of a group share a long common prefix; a cache hit returns the same `Pattern` without compiling, except with `re.DEBUG` |
| `Pattern.match(string[, pos[, endpos]])` | O(m) | O(c) | One attempt, at `pos` |
| `Pattern.fullmatch(string[, pos[, endpos]])` | O(m) | O(c) | One attempt, which must end at `endpos` |
| `Pattern.search(string[, pos[, endpos]])` | O(s) | O(c) | Retries at successive start positions until one matches |
| `Pattern.findall(string[, pos[, endpos]])` | O(s + g) | O(k + g) | One string per match, or a tuple of c group strings when there are two or more groups, O(k·c + g) |
| `Pattern.finditer(string[, pos[, endpos]])` | O(c) | O(c) | Nothing is scanned until the first `next()` |
| Iterating a `finditer()` | O(s) in total | O(c) per match | Each step scans forward to the next match |
| `Pattern.sub(repl, string, count=0)` | O(s + t + k·t + r) | O(k + t + r) | The result is joined from a list of pieces; a `repl` with backreferences is parsed on first use and then served from a cache, and expanded at every match, O(t) even where its groups are empty; a function `repl` adds O(f) per match |
| `Pattern.subn(repl, string, count=0)` | O(s + t + k·t + r) | O(k + t + r) | `sub()` that also returns the number of replacements |
| `Pattern.split(string, maxsplit=0)` | O(s + m + k·c + g) | O(m + k·c + g) | k + 1 pieces, plus c group strings per match when the pattern captures |
| `Pattern.pattern`, `Pattern.flags`, `Pattern.groups` | O(1) | O(1) | Stored with the compiled pattern |
| `Pattern.groupindex` | O(1) | O(1) | The name-to-number mapping, returned without copying it |

### Module-level functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.match(pattern, string, flags=0)`, `re.fullmatch(pattern, string, flags=0)`, `re.search(pattern, string, flags=0)` | `re.compile` + the method | `re.compile` + the method | The pattern is compiled on a cache miss and looked up on a hit |
| `re.findall(pattern, string, flags=0)`, `re.finditer(pattern, string, flags=0)` | `re.compile` + the method | `re.compile` + the method | As above |
| `re.sub(pattern, repl, string, count=0, flags=0)`, `re.subn(pattern, repl, string, count=0, flags=0)` | `re.compile` + the method | `re.compile` + the method | As above |
| `re.split(pattern, string, maxsplit=0, flags=0)` | `re.compile` + the method | `re.compile` + the method | As above |
| `re.escape(pattern)` | O(n) | O(n) | n = length of the string escaped |
| `re.purge()` | O(1) | O(1) | Empties caches of a fixed maximum size; each pattern then compiles again on its next use |

### Match

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Match.start([group])`, `Match.end([group])`, `Match.span([group])` | O(1) | O(1) | Positions the match already holds |
| `Match.group([group1, ...])`, `match[group]` | O(g) | O(g) | Copies the text out of the subject; a group spanning the whole of an exact `str` or `bytes` subject returns the subject itself. q arguments return a tuple, O(q + g) |
| `Match.groups(default=None)` | O(c + g) | O(c + g) | One copy per capturing group |
| `Match.groupdict(default=None)` | O(c + g) | O(c + g) | The same copies, keyed by name, for the named groups only |
| `Match.expand(template)` | O(t + g) | O(t + g) | The template's text plus the groups it refers to |
| `Match.pos`, `Match.endpos`, `Match.lastindex`, `Match.lastgroup`, `Match.re` | O(1) | O(1) | Stored with the match |
| `Match.string` | O(1) | O(1) | The subject itself, not a copy: a live match keeps the whole subject alive |

### Flags and exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `re.ASCII`, `re.IGNORECASE`, `re.LOCALE`, `re.MULTILINE`, `re.DOTALL`, `re.VERBOSE`, `re.UNICODE`, `re.DEBUG` | O(1) | O(1) | With the one-letter aliases `re.A`, `re.I`, `re.L`, `re.M`, `re.S`, `re.X`, `re.U` |
| `re.NOFLAG` | O(1) | O(1) | Python 3.11+ |
| `re.RegexFlag` | O(1) | O(1) | The `enum.IntFlag` the constants belong to |
| `re.Pattern`, `re.Match` | O(1) | O(1) | The types `compile()` and the matching methods return |
| `re.error`, `re.PatternError` | O(1) | O(1) | Raised by `compile()` for an invalid pattern; `PatternError` is the Python 3.13+ name, `error` an alias |
| `PatternError.msg`, `PatternError.pattern`, `PatternError.pos`, `PatternError.lineno`, `PatternError.colno` | O(1) | O(1) | Filled in when the error is raised |

## Matching Costs

### One Attempt or Many

`match()` and `fullmatch()` make one attempt at one position. `search()` makes an attempt at each
position until one succeeds, and `findall()`, `finditer()`, `sub()` and `split()` are that search
repeated. When each attempt stops quickly the whole scan is linear; when each can run to the end
of the subject, m attempts of O(m) make it quadratic. For `\w+@`, a word boundary stops every
attempt that starts inside a word, which brings the scan back to linear.

```python
import re

word = 'a' * 2_000

email_ish = re.compile(r'\w+@')
assert email_ish.match(word) is None   # O(m) - one attempt
assert email_ish.search(word) is None  # O(m²) - every start position scans to the end

# A word boundary fails at once inside the word, so only one attempt runs far
bounded = re.compile(r'\b\w+@')
assert bounded.search(word) is None    # O(m)

# Both find the same match
text = 'mail alice@example.com'
assert email_ish.search(text).group() == bounded.search(text).group() == 'alice@'
```

### Catastrophic Backtracking

The blow-up needs an attempt that *fails*. `(a+)+b` against a string of `a`s with a `b` at the
end matches on the first attempt; take the `b` away and the matcher tries every way of splitting
the `a`s between the two repetitions before giving up.

```python
import re
import sys

# AVOID: nested quantifiers, on input that does not match
bad_pattern = re.compile(r'(a+)+b')
assert bad_pattern.search('a' * 8 + 'b')  # matches at once
assert bad_pattern.search('a' * 8) is None  # exponential in m, harmless at this size
# bad_pattern.search('a' * 24)  # doubles with each extra 'a' - do not run

# BETTER: remove the nesting, so there is nothing to redistribute
good_pattern = re.compile(r'a+b')
assert good_pattern.search('a' * 24) is None  # O(m²) at worst

# Python 3.11+: keep the nesting but forbid the backtracking
if sys.version_info >= (3, 11):
    atomic = re.compile(r'(?>a+)+b')
    possessive = re.compile(r'(a++)+b')
    assert atomic.search('a' * 24) is None
    assert possessive.search('a' * 24) is None
```

### Anchoring a Search

A pattern that cannot match anywhere still costs a `search()` a pass over every position. From
Python 3.11 a pattern starting with `^` (without `re.MULTILINE`) or `\A` stops after the first
attempt, which is where anchoring saves time. Before 3.11 the retries ran anyway and failed on the
anchor at each position. Where the match is at the start, there is nothing to save on any version.

```python
import re

unanchored = re.compile(r'start.*end')
anchored = re.compile(r'^start.*end')

# No match anywhere: from 3.11 the anchored search makes one attempt
haystack = 'x' * 100_000
assert unanchored.search(haystack) is None  # O(m) - scans every position
assert anchored.search(haystack) is None    # O(1) from 3.11, O(m) before

# match() is anchored on every version
assert unanchored.match(haystack) is None   # O(1) - one attempt fails at once
```

## Match Objects

A match holds the subject and two positions per group. Reading a position is O(1); asking for
the text copies it. When only the positions matter, `span()` avoids building the substring.

```python
import re

pattern = re.compile(r'(\d+)-(?P<word>\w+)')
text = 'id: 123-abc'

match = pattern.search(text)  # O(s)
assert match.span(1) == (4, 7)  # O(1) - nothing is copied
assert text[slice(*match.span(1))] == '123'

assert match.group(0) == '123-abc'  # O(g) - copies the matched text
assert match[1] == '123'            # O(g) - same as group(1)
assert match.groups() == ('123', 'abc')         # O(c + g)
assert match.groupdict() == {'word': 'abc'}     # named groups only
assert match.expand(r'\g<word>=\1') == 'abc=123'  # O(t + g)

assert match.string is text  # O(1) - the subject itself, kept alive by the match
assert match.lastindex == 2 and match.lastgroup == 'word'
assert pattern.groupindex['word'] == 2  # O(1) - not a copy
```

## Finding All Matches

`findall()` builds every result before it returns; `finditer()` hands back one match at a time,
so memory follows the match rather than the number of matches. The scan costs the same either
way.

```python
import re

pattern = re.compile(r'\w+')
text = ' '.join(f'word{i}' for i in range(10_000))

# EAGER: O(k + g) memory - every match copied into one list
words = pattern.findall(text)  # O(s + g)
assert len(words) == 10_000

# LAZY: O(c) memory per match, one alive at a time
longest = 0
for match in pattern.finditer(text):  # O(s) over the whole iteration
    longest = max(longest, match.end() - match.start())  # O(1) - no copy
assert longest == len('word9999')

# With two or more groups, each item is a tuple of the groups
pairs = re.compile(r'(\w)(\d)').findall('a1 b2')
assert pairs == [('a', '1'), ('b', '2')]
```

## Substitution and Splitting

`sub()` joins a list of pieces into a new string, so its space is the result's length plus a
list entry or two per match. A string replacement is parsed once and cached; a function
replacement is called once per match, and its cost adds to every one.

```python
import re

pattern = re.compile(r'\d+')
text = 'Numbers: 10, 20, 30'

assert pattern.sub('X', text) == 'Numbers: X, X, X'  # O(s + r)
assert pattern.subn('X', text) == ('Numbers: X, X, X', 3)
assert pattern.sub('X', text, count=1) == 'Numbers: X, 20, 30'

# A function repl: O(s + r + k·f)
def double(match):
    return str(int(match.group()) * 2)

assert pattern.sub(double, text) == 'Numbers: 20, 40, 60'

# split() returns the pieces, and the groups' text when the pattern captures
assert re.split(r',\s*', 'apple, banana, cherry') == ['apple', 'banana', 'cherry']
assert re.split(r'(,)\s*', 'a, b') == ['a', ',', 'b']
assert re.split(r',\s*', 'a, b, c', maxsplit=1) == ['a', 'b, c']
```

## The Pattern Cache

The module-level functions compile their pattern through a cache of up to 512 entries, so
calling `re.search(p, s)` in a loop compiles `p` once and then looks it up. A new pattern arriving
at a full cache drops one entry, not the whole cache. Reusing a `Pattern` from `re.compile()`
skips the lookup and does not depend on the cache at all.

```python
import re

re.purge()  # O(1) - empties the caches
first = re.compile(r'\d+')   # O(n) - compiled and cached
second = re.compile(r'\d+')  # cache hit - no recompilation
assert first is second

lines = ['no digits here', 'order 66', 'still nothing']

# Works, but looks the pattern up in the cache on every call
assert [line for line in lines if re.search(r'\d+', line)] == ['order 66']

# Compiled once: each call is only the O(s) scan
digits = re.compile(r'\d+')
assert [line for line in lines if digits.search(line)] == ['order 66']

# An invalid pattern raises when it is compiled
try:
    re.compile(r'(unclosed')
except re.error as error:
    assert error.pos == 0 and error.lineno == 1
else:
    raise AssertionError('an invalid pattern compiled')

# re.escape() makes a literal pattern out of any string - O(n)
assert re.escape('a.b*c') == 'a\\.b\\*c'
assert re.fullmatch(re.escape('a.b*c'), 'a.b*c')
```

## Common Patterns

### Tokenizing

One alternation of named groups, iterated with `finditer()`, tokenizes in a single scan and holds
one match at a time. `lastgroup` names the branch that matched in O(1).

```python
import re

token = re.compile(r'(?P<num>\d+)|(?P<name>[a-z]+)|(?P<op>[+*=])|(?P<space>\s+)')

tokens = [
    (match.lastgroup, match.group())  # O(1) + O(g)
    for match in token.finditer('x = 12 + y')  # O(s) in total
    if match.lastgroup != 'space'
]
assert tokens == [('name', 'x'), ('op', '='), ('num', '12'), ('op', '+'), ('name', 'y')]
```

## Performance Best Practices

✅ **Do**:

- Compile a pattern once and reuse the `Pattern`, rather than relying on the cache lookup in a loop
- Use `finditer()` when the matches are consumed one at a time, so memory follows one match
- Use `span()`, `start()` and `end()` when the positions are enough; they copy nothing
- Anchor a pattern that must match at the start with `^` or `\A`, or call `match()`; from 3.11 a
  failing anchored `search()` stops after one attempt, unless `^` is under `re.MULTILINE`
- Start a pattern with something that fails fast, such as `\b`, when its failed attempts would
  otherwise run to the end of the subject

❌ **Avoid**:

- Nested or competing quantifiers such as `(a+)+` and `a*a*` on input that may not match; remove
  the nesting, or on Python 3.11+ make the inner repetition atomic, `(?>a+)+`, or possessive,
  `(a++)+`
- `search()` with a pattern like `\w+@` on long runs of word characters - quadratic in the run
- `findall()` on a large subject when you only walk the results once
- Keeping `Match` objects from a large subject alive longer than needed; each one holds the subject

## Version Notes

- **Python 3.11+**: Atomic groups `(?>...)` and possessive quantifiers `*+`, `++`, `?+`, which
  never give back what they matched: made atomic, the inner repetition of `(a+)+b` can no longer
  trade characters with the outer one
- **Python 3.11+**: A `search()` whose pattern starts with `\A`, or with `^` without
  `re.MULTILINE`, stops after the first attempt instead of retrying at every position
- **Python 3.13+**: `re.PatternError` is the exception's name, with `re.error` kept as an alias

## Related Modules

- **[fnmatch](fnmatch.md)** - shell-style wildcards, translated to a cached regular expression
- **[string](string.md)** - `Template`, whose placeholders are found with a regular expression
- **[str](../builtins/str.md)** - `in`, `find()` and `split()` for a fixed substring, with no
  pattern to compile
