# textwrap Module Complexity

The `textwrap` module reformats plain text: `wrap()` and `fill()` break a paragraph into lines no
wider than `width`, `shorten()` cuts one down to a single line, and `dedent()` and `indent()`
adjust leading whitespace line by line. It is pure Python over `str` methods and a few regular
expressions compiled at import, and every function reads the whole text and builds its whole
result in memory.

`n` is the characters of the input text, counted after tab expansion for the wrapping functions,
and `m` is its lines. `w` is the width a wrapped line has left after its indent, `k` is the length
of the longest word (run of non-whitespace characters), and `p` is the length of the `indent()`
prefix. Whitespace at the start of the text counts as a word, and so does every run of whitespace
with `drop_whitespace=False`. The bounds treat `initial_indent`, `subsequent_indent` and
`placeholder` as constant length and shorter than `width`; an `indent()` predicate is called once
per line and its cost adds to the row.

## Complexity Reference

### Module functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `textwrap.wrap(text, width=70, **kwargs)` | O(n + n·k/w) | O(n) | Builds a `TextWrapper` and calls its `wrap()`; the n·k/w term is words longer than a line |
| `textwrap.fill(text, width=70, **kwargs)` | O(n + n·k/w) | O(n) | `wrap()` joined with newlines |
| `textwrap.shorten(text, width, **kwargs)` | O(n) | O(n) | Collapses whitespace and splits the whole text, although the result is at most `width` characters |
| `textwrap.dedent(text)` | O(n) | O(n) | Lines of only spaces and tabs become empty and do not count towards the common margin |
| `textwrap.indent(text, prefix, predicate=None)` | O(n + m·p) | O(n + m·p) | Calls `predicate` once per line; by default every line with a non-whitespace character is prefixed |

### TextWrapper

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `textwrap.TextWrapper(width=70, initial_indent='', subsequent_indent='', ...)` | O(1) | O(1) | Stores its options; the word-splitting expressions are compiled once, at import |
| `TextWrapper.wrap(text)` | O(n + n·k/w) | O(n) | Splits the whole text into words before building the first line; a word longer than a line is split one line at a time, copying the rest of the word each time |
| `TextWrapper.fill(text)` | O(n + n·k/w) | O(n) | `wrap()` joined with newlines |
| `TextWrapper.width`, `TextWrapper.initial_indent`, `TextWrapper.subsequent_indent` | O(1) | O(1) | Read on every call, so a change applies from the next `wrap()` or `fill()` |
| `TextWrapper.expand_tabs`, `TextWrapper.tabsize`, `TextWrapper.replace_whitespace`, `TextWrapper.drop_whitespace` | O(1) | O(1) | Whitespace handling; `shorten()` collapses whitespace first, so they have no effect there |
| `TextWrapper.break_long_words`, `TextWrapper.break_on_hyphens` | O(1) | O(1) | `break_long_words=False` puts an over-long word on a line of its own instead of cutting it, which removes the n·k/w term; `break_on_hyphens` still breaks it after a hyphen |
| `TextWrapper.fix_sentence_endings` | O(1) | O(1) | Puts two spaces after a sentence-ending word |
| `TextWrapper.max_lines`, `TextWrapper.placeholder` | O(1) | O(1) | Stops after `max_lines` lines and appends `placeholder`; the whole text is still split first |

## Wrapping Text

### wrap and fill

`wrap()` returns the lines; `fill()` is the same lines joined with newlines, so neither is cheaper
than the other. Both treat the text as one paragraph: newlines are whitespace like any other.

```python
import textwrap

text = "The quick brown fox jumps over the lazy dog"

lines = textwrap.wrap(text, width=20)  # O(n)
assert lines == ['The quick brown fox', 'jumps over the lazy', 'dog']

filled = textwrap.fill(text, width=20)  # O(n)
assert filled == '\n'.join(lines)

# A newline is only whitespace: the paragraph is refilled
assert textwrap.wrap("one\ntwo", width=20) == ['one two']
```

### Words Longer Than a Line

A word that does not fit on any line is broken one line at a time, and each break copies the rest
of the word. A single word of n characters therefore costs O(n²/w), which is what a long URL or a
base64 blob hits. `break_long_words=False` puts the word on a line of its own instead, and for a
string with no whitespace or hyphens, slicing gives the same lines in O(n).

```python
import textwrap

blob = "x" * 10_000

lines = textwrap.wrap(blob, width=76)  # O(n·k/w) - one copy of the rest per line
assert len(lines) == 132 and lines[0] == "x" * 76

# Slicing reaches the same lines in O(n)
assert [blob[i:i + 76] for i in range(0, len(blob), 76)] == lines

# Kept whole: O(n), on one over-wide line
assert textwrap.wrap(blob, width=76, break_long_words=False) == [blob]
```

### Reusing a TextWrapper

The module functions build a `TextWrapper` on every call. That costs O(1) - the expressions it
splits with are compiled at import - so a reused wrapper saves only the construction. Its options
are plain attributes, read again on each call.

```python
import textwrap

wrapper = textwrap.TextWrapper(width=20, initial_indent="* ", subsequent_indent="  ")  # O(1)
text = "one two three four five six seven"

assert wrapper.wrap(text) == ['* one two three four', '  five six seven']  # O(n)

wrapper.width = 12  # O(1) - applies from the next call
assert wrapper.fill(text) == '* one two\n  three four\n  five six\n  seven'
```

## Truncating Text

`shorten()` returns at most `width` characters, but it collapses the whitespace of the whole text
and splits all of it into words first, so it is O(n) however small `width` is. `max_lines` works
the same way: `wrap()` stops building lines once it has enough, after splitting the whole text.

```python
import textwrap

text = "The quick brown fox jumps over the lazy dog"

assert textwrap.shorten(text, width=20) == 'The quick [...]'  # O(n)
assert textwrap.shorten(text, width=20, placeholder="...") == 'The quick brown...'
assert textwrap.shorten("Hello   world!", width=12) == 'Hello world!'

# O(n) - the whole text is split before the first line is built
assert textwrap.wrap(text, width=15, max_lines=2) == ['The quick brown', 'fox jumps [...]']
```

## Adjusting Indentation

### dedent

`dedent()` finds the longest run of spaces and tabs that starts every line, ignoring lines of only
spaces and tabs, and removes it. Tabs and spaces are different characters here, so a tab-indented line and a
space-indented one share no margin.

```python
import textwrap

source = """
    def hello():
        return "hi"
"""

assert textwrap.dedent(source) == '\ndef hello():\n    return "hi"\n'  # O(n)

# A line of only spaces and tabs becomes empty and does not narrow the margin
assert textwrap.dedent("  a\n    \n  b") == 'a\n\nb'

# A tab is not a run of spaces
assert textwrap.dedent("  a\n\tb") == '  a\n\tb'
```

### indent

`indent()` adds the prefix to each selected line, so its output grows by the prefix length for
every line it prefixes. The predicate sees each line once, with its line ending.

```python
import textwrap

text = "first\n\nsecond\n"

# O(n + m·p) - the blank line is skipped by default
assert textwrap.indent(text, "> ") == '> first\n\n> second\n'

seen = []

def every_line(line):
    seen.append(line)
    return True

assert textwrap.indent(text, "> ", every_line) == '> first\n> \n> second\n'
assert seen == ['first\n', '\n', 'second\n']  # one call per line
```

## Common Patterns

### Filling Several Paragraphs

`fill()` refills everything it is given as one paragraph, so split on blank lines first to keep
paragraph breaks.

```python
import textwrap

document = "First paragraph, long enough to wrap.\n\nSecond one."

paragraphs = document.split("\n\n")  # O(n)
wrapped = "\n\n".join(textwrap.fill(p, width=20) for p in paragraphs)  # O(n)

assert wrapped == 'First paragraph,\nlong enough to wrap.\n\nSecond one.'
```

### Formatting an Indented Block

```python
import textwrap

usage = textwrap.dedent("""\
    Usage: tool [options]
    Reads its input and writes a report.
""")  # O(n)

block = textwrap.indent(usage, "    ")  # O(n + m·p)
assert block == '    Usage: tool [options]\n    Reads its input and writes a report.\n'
```

## Performance Best Practices

✅ **Do**:

- Pass `break_long_words=False` when the text may hold a very long word such as a URL or an encoded
  blob and an over-wide line is acceptable; cutting the word costs O(n²/w)
- Slice a string with no whitespace or hyphens into lines yourself rather than wrapping it
- Reuse a `TextWrapper` for many calls with the same options if it reads better; it saves only an
  O(1) construction

❌ **Avoid**:

- Expecting `fill()` to beat `'\n'.join(wrap())`; it is exactly that
- Wrapping a multi-paragraph document in one call, which merges the paragraphs
- Expecting `shorten()` or `max_lines` to read only what they return; the whole text is still split

## Version Notes

- **Python 3.3+**: Added `indent()` and `TextWrapper.tabsize`
- **Python 3.4+**: Added `shorten()`, `TextWrapper.max_lines` and `TextWrapper.placeholder`

## Related Modules

- **[str](../builtins/str.md)** - the string methods these functions are built from
- **[re](re.md)** - the regular expressions `TextWrapper` splits words with
- **[pprint](pprint.md)** - width-limited formatting of Python objects rather than prose
