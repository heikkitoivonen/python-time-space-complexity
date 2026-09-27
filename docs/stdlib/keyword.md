# keyword Module Complexity

The `keyword` module lists Python's keywords and soft keywords and tests whether a string is one.
Both lists are built when the module is imported, and each test is a lookup in a `frozenset` made
from its list at the same time, so nothing here grows with the number of keywords.

`n` is the characters in the string being tested. The keyword lists are fixed for an interpreter
version, so their length is a constant rather than a size variable.

## Complexity Reference

### Keyword checks

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `keyword.iskeyword(s)` | O(n) | O(1) | Hashes `s`, then one set lookup; `str` caches its hash, so the same object again is O(1) |
| `keyword.issoftkeyword(s)` | O(n) | O(1) | The same lookup against the soft keywords |

### Keyword lists

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `keyword.kwlist` | O(1) | O(1) | The hard keywords, sorted |
| `keyword.softkwlist` | O(1) | O(1) | The soft keywords, sorted; none of them is in `kwlist` |

## Checking Identifiers

### Is a String a Keyword

`iskeyword()` is a set lookup, not a scan of `kwlist`: it compares `s` only with an entry whose
hash matches. The test is exact and case-sensitive.

```python
import keyword

assert keyword.iskeyword('if')           # O(n)
assert keyword.iskeyword('None')         # O(n)
assert not keyword.iskeyword('variable') # O(n)
assert not keyword.iskeyword('If')       # case matters
assert not keyword.iskeyword('print')    # a builtin, not a keyword

assert 'if' in keyword.kwlist            # O(1) access, then a scan of the list
assert keyword.kwlist == sorted(keyword.kwlist)
```

### Hard vs Soft Keywords

A soft keyword is a keyword only in certain positions, so it stays usable as a name elsewhere.
The two lists do not overlap: check both when a string must not read as either.

```python
import keyword

assert keyword.issoftkeyword('match')    # O(n)
assert not keyword.iskeyword('match')    # a valid variable name
assert keyword.issoftkeyword('_')

assert not set(keyword.kwlist) & set(keyword.softkwlist)

match = 1  # soft keywords can still be assigned
assert match == 1
```

## Common Patterns

### Validating a Generated Name

Identifier syntax and not being a hard keyword are the two checks a name needs from `str` and
`keyword`; each is linear in the string, so together they are O(n).

```python
import keyword

def is_name(s):
    return s.isidentifier() and not keyword.iskeyword(s)  # O(n)

assert is_name('klass')
assert not is_name('class')
assert not is_name('2fast')
assert is_name('case')  # a soft keyword is a legal name
```

## Performance Best Practices

✅ **Do**:

- Use `iskeyword()` to test a string: one hash and one set lookup

❌ **Avoid**:

- `s in keyword.kwlist` - a scan that compares `s` against every entry before it can say no

## Version Notes

- **Python 3.12+**: `'type'` is a soft keyword, so `issoftkeyword('type')` is `True`

## Related Modules

- **[token](token.md)** - the token type constants the tokenizer emits
- **[tokenize](tokenize.md)** - tokenizing source text, which reports keywords as `NAME` tokens
