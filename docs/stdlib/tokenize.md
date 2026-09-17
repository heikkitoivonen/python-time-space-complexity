# tokenize Module Complexity

The `tokenize` module lexes Python source into `TokenInfo` tuples. Its two
generators pull one line at a time through the `readline` callable they are
given and yield each token as soon as the line holding it has been read, so
the cost of tokenizing is linear in the source and the memory it holds is a
line, or one token where a token spans lines, however long the file. `untokenize()` is the reverse: it writes source
back from tokens and, given full five-tuples, rebuilds the spacing between
them from their positions. Encoding detection reads at most two lines.

## Complexity Reference

Size variables: n = characters of source; t = tokens yielded; L = characters
in the longest line, or in the longest token when one spans lines, such as a
triple-quoted string; h = bytes in the lines `detect_encoding()` reads, at
most two; c = characters in the source `untokenize()` produces.

### Tokenizing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `generate_tokens(readline)` | O(n) | O(L) | Lazy. Calls `readline` for one line at a time, never ahead of the token being yielded, and drops each line once the next begins unless a token spans them. Stopping after k tokens costs the lines read to reach them |
| `tokenize(readline)` | O(n) | O(L) | `detect_encoding()` first, then decodes each line as it is read. The first token yielded is `ENCODING` |
| `TokenInfo` fields, `exact_type` | O(1) | O(1) | Tokens on one line share one `line` string, so a list of every token holds each line once: O(t + n), not O(t·L) |
| `TokenError` | — | — | Raised from inside the stream, so the tokens of the lines before the fault have already been yielded. Up to 3.11 it is raised only for an EOF inside a string, a bracket or a backslash continuation, and a malformed token is yielded as `ERRORTOKEN` with tokenizing continuing; from 3.12 an unterminated string or a NUL byte raises it too. An inconsistent dedent raises `IndentationError` instead, on every version |
| `tok_name` | O(1) | O(1) | Token type to its name; `exact_type` names the operator itself |

From 3.12 an f-string is tokenized into its parts, `FSTRING_START`, an
`FSTRING_MIDDLE` per run of literal text, the expression's own tokens and
`FSTRING_END`, where 3.10 and 3.11 yield one `STRING`; 3.14 does the same for
t-strings. That raises t for the same n.

### Encodings

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `detect_encoding(readline)` | O(h) | O(h) | Reads the first line, and the second only when the first is blank or a comment without a cookie. Decodes what it read to validate the codec, and returns those lines so the caller need not read them again |
| `open(filename)` | O(h) | O(h) | `detect_encoding()` on the file, then seeks back to the start and wraps it in a text stream with that encoding. Nothing else is read until the caller reads |

### Reversing

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `untokenize(iterable)` | O(t + c) | O(t + c) | Five-tuples: the whitespace between tokens is regenerated from their positions, so a gap of k columns costs k spaces and adjacent tokens cost none. Two-tuples: positions are gone and the spacing is the module's own. Returns bytes when the stream starts with `ENCODING`, str otherwise |
| `python -m tokenize [-e] [file]` | as `tokenize()` | O(t + n) with a file | A file argument lists every token, and with them every line, before printing the first, so a source that fails prints nothing but the error. Standard input streams, and a fault prints the tokens before it |

## Reading stays one line ahead

`generate_tokens()` reads nothing until it is first advanced, and then only
the line holding the next token; `tokenize()` adds the line or two that settle
the encoding. Scanning for one name near the top of a file costs the lines up
to it, not the file. A list of every token is larger than
the tokens: each carries its line, but the tokens on one line carry the same
string, so the list holds each line once.

```python
import io
import tokenize

source = "first = 1\nsecond = 2\n" * 1000
stream = io.StringIO(source)
calls = 0


def readline():
    global calls
    calls += 1
    return stream.readline()


tokens = tokenize.generate_tokens(readline)  # nothing read yet - O(1)
assert calls == 0

first = next(tokens)  # reads line 1 and no further - O(L)
assert first.string == "first" and calls == 1

# Stop early and pay for the lines read, not the source - O(their characters)
for token in tokens:
    if token.string == "second":
        break
assert calls == 2

# Every token on a line shares one line string - O(t + n) for the whole list
every = list(tokenize.generate_tokens(io.StringIO("total = a + b\n").readline))
assert all(token.line is every[0].line for token in every[:-1])
assert every[-1].type == tokenize.ENDMARKER and every[-1].line == ""
```

## Encoding detection reads at most two lines

`detect_encoding()` stops at the first line that settles the question: a
coding cookie, or any line that is neither blank nor a comment. A byte-order
mark alone does not settle it, because a cookie on the second line could
still contradict it. Only when the first line settles nothing is a second
read, and never a third. `tokenize.open()` runs the same detection and then
rewinds, so the text stream it returns starts at the first byte.

```python
import io
import pathlib
import tempfile
import tokenize


def counting(data):
    stream = io.BytesIO(data)
    calls = []

    def readline():
        calls.append(1)
        return stream.readline()

    return readline, calls


body = b"x = 1\n" * 10_000

readline, calls = counting(b"# -*- coding: latin-1 -*-\n" + body)
encoding, consumed = tokenize.detect_encoding(readline)  # one line - O(h)
assert (encoding, len(consumed), len(calls)) == ("iso-8859-1", 1, 1)

readline, calls = counting(b"#!/usr/bin/env python\n# coding: latin-1\n" + body)
encoding, consumed = tokenize.detect_encoding(readline)  # two lines - O(h)
assert (encoding, len(consumed), len(calls)) == ("iso-8859-1", 2, 2)

readline, calls = counting(b"import os\n" + body)
encoding, consumed = tokenize.detect_encoding(readline)  # code on line 1: stops there
assert (encoding, len(calls)) == ("utf-8", 1)

with tempfile.TemporaryDirectory() as tmp:
    path = pathlib.Path(tmp) / "latin.py"
    path.write_bytes(b"# coding: latin-1\nname = '\xe9'\n")
    with tokenize.open(path) as file:  # detects, then seeks back - O(h)
        assert file.encoding == "iso-8859-1"
        assert file.read() == "# coding: latin-1\nname = '\u00e9'\n"
```

## Spacing comes from positions

Given the five-tuples the generators yield, `untokenize()` places each token
at its recorded column and fills the gap with spaces, so the spaces between
the tokens on a line come back as they were, a tab between two tokens comes
back as one space, and dropping a token leaves its gap behind. Given two-tuples of type
and string it has no positions, and separates tokens by rules of its own.

```python
import io
import tokenize

source = "if x:\n    y = 1  # note\n"
tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))

# Five-tuples: the spacing is rebuilt from the recorded columns - O(t + c)
assert tokenize.untokenize(tokens) == source

# Dropping a token keeps the others' columns, and the gap it leaves - O(c)
kept = [token for token in tokens if token.type != tokenize.COMMENT]
assert tokenize.untokenize(kept) == "if x:\n    y = 1        \n"

# Two-tuples: the positions are gone, so the spacing is the module's own
loose = tokenize.untokenize((token.type, token.string) for token in tokens)
assert loose == "if x :\n    y =1 # note\n"

# A stream that began with ENCODING comes back as bytes
raw = list(tokenize.tokenize(io.BytesIO(b"x = 1\n").readline))
assert tokenize.untokenize(raw) == b"x = 1\n"
```

## Errors arrive in the stream

`TokenError` is raised by the generator when it reaches the fault, so every
token of the lines before it has already been yielded. A consumer that keeps
what it has seen keeps the prefix that tokenized.

```python
import io
import tokenize

seen = []
try:
    for token in tokenize.generate_tokens(io.StringIO("total = (1,\n").readline):
        seen.append(token.string)  # each yielded before the fault is reached
except tokenize.TokenError as error:
    message, position = error.args
    assert "EOF in multi-line statement" in message

assert seen == ["total", "=", "(", "1", ",", "\n"]
```

The command line prints what `tokenize()` yields, one token per line:

```bash
# Tokenize a file - O(n), but every token is listed before the first is printed
python -m tokenize script.py

# Name each operator exactly (EQUAL, LPAR) instead of OP
python -m tokenize -e script.py

# From standard input the tokens stream, and a fault prints the ones before it
python -m tokenize < script.py
```

## Related Documentation

- [token Module](token.md)
- [ast Module](ast.md)
- [keyword Module](keyword.md)
- [io Module](io.md)
