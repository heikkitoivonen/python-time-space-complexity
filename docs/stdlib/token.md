# token Module Complexity

The `token` module holds the integer constants that name Python's token types, a dictionary from
each value back to its name, a dictionary from each operator string to its specific type, and
three one-line predicates. It does no tokenizing itself: `tokenize` produces the tokens, and this
module only labels them.

Everything here is built once, when the module is imported, and every lookup afterwards is a dict
lookup or an integer comparison. No operation on the page depends on the size of the source being
tokenized.

## Complexity Reference

### Token type constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `token.ENDMARKER`, `token.NAME`, `token.NUMBER`, `token.STRING`, `token.NEWLINE`, `token.INDENT`, `token.DEDENT`, `token.OP` | O(1) | O(1) | Small integers; several are renumbered between Python releases, so compare against the name, never a literal |
| `token.COMMENT`, `token.NL`, `token.ENCODING`, `token.ERRORTOKEN`, `token.TYPE_COMMENT`, `token.TYPE_IGNORE`, `token.SOFT_KEYWORD` | O(1) | O(1) | |
| `token.FSTRING_START`, `token.FSTRING_MIDDLE`, `token.FSTRING_END` | O(1) | O(1) | Python 3.12+ |
| `token.TSTRING_START`, `token.TSTRING_MIDDLE`, `token.TSTRING_END` | O(1) | O(1) | Python 3.14+ |
| `token.AWAIT`, `token.ASYNC` | O(1) | O(1) | Python 3.12 and earlier |
| Operator constants: `token.LPAR`, `token.PLUS`, `token.NOTEQUAL`, ... | O(1) | O(1) | One per key of `EXACT_TOKEN_TYPES` |
| `token.N_TOKENS` | O(1) | O(1) | One more than the largest token type value |
| `token.NT_OFFSET` | O(1) | O(1) | 256; values at or above it are grammar nonterminals, not tokens |

### Lookups and predicates

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `token.tok_name[type]` | O(1) | O(1) | Dict lookup from value to name, built once at import |
| `token.EXACT_TOKEN_TYPES[string]` | O(1) | O(1) | Dict lookup from an operator string to its specific type; `TokenInfo.exact_type` gives the same answer |
| `token.ISTERMINAL(x)` | O(1) | O(1) | `x < NT_OFFSET` |
| `token.ISNONTERMINAL(x)` | O(1) | O(1) | `x >= NT_OFFSET` |
| `token.ISEOF(x)` | O(1) | O(1) | `x == ENDMARKER` |

## Naming Token Types

`tokenize` hands back each token's type as an integer. `tok_name` turns it back into a name with
one dict lookup per token.

```python
import io
import token
import tokenize

code = "x = 1 + 2"

tokens = tokenize.generate_tokens(io.StringIO(code).readline)
names = [(token.tok_name[tok.type], tok.string) for tok in tokens]  # O(1) per token

assert names == [
    ('NAME', 'x'),
    ('OP', '='),
    ('NUMBER', '1'),
    ('OP', '+'),
    ('NUMBER', '2'),
    ('NEWLINE', ''),
    ('ENDMARKER', ''),
]
```

## Generic and Exact Operator Types

`tokenize` reports every operator as the generic `OP`. The specific type is one lookup away,
either through `EXACT_TOKEN_TYPES` or through the token's own `exact_type`.

```python
import io
import token
import tokenize

tokens = list(tokenize.generate_tokens(io.StringIO("a != b\n").readline))
op = tokens[1]

assert op.type == token.OP
assert token.EXACT_TOKEN_TYPES[op.string] == token.NOTEQUAL  # O(1)
assert op.exact_type == token.NOTEQUAL  # O(1)
assert token.tok_name[op.exact_type] == 'NOTEQUAL'  # O(1)

assert token.ISTERMINAL(op.type)  # O(1)
assert not token.ISNONTERMINAL(op.type)  # O(1)
assert token.ISEOF(tokens[-1].type)  # O(1) - the last token is ENDMARKER
```

## Performance Best Practices

✅ **Do**:

- Compare a token's type against the named constant, such as `tok.type == token.NAME`
- Use `exact_type` to tell operators apart; `type` is `OP` for every one of them

❌ **Avoid**:

- Writing a token type as a number, or storing numbers across interpreter versions: the values
  are renumbered when token types are added or removed

## Version Notes

- **Python 3.12+**: Added `EXCLAMATION`, `FSTRING_START`, `FSTRING_MIDDLE` and `FSTRING_END`
- **Python 3.13+**: Removed `AWAIT` and `ASYNC`
- **Python 3.14+**: Added `TSTRING_START`, `TSTRING_MIDDLE` and `TSTRING_END`
- **All Python 3**: Token type values are not stable between releases

## Related Modules

- **[tokenize](tokenize.md)** - produces the tokens these constants label
- **[keyword](keyword.md)** - tells which `NAME` tokens are keywords
