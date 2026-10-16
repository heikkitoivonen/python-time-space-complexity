# xml Module

The `xml` package contains interfaces for parsing and manipulating XML documents.
Operation complexities and examples are documented on the interface pages:

- [ElementTree](xml.etree.elementtree.md) — `xml.etree.ElementTree`: parsing,
  searching, building and serializing element trees.
- [DOM](xml.dom.md) — `xml.dom`, `xml.dom.minidom` and `xml.dom.pulldom`: document objects, DOM
  traversal and partial DOM trees built from a stream.
- [SAX](xml.sax.md) — `xml.sax` and its submodules: parsing with event handlers.
- [Expat](pyexpat.md) — `xml.parsers.expat`, which re-exports `pyexpat`: the Expat parser
  interface.

The package itself holds two string checks, added in Python 3.15. `n` is the characters in the
string checked.

## Complexity Reference

### Validation helpers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `xml.is_valid_name(name)` | O(n) | O(1) | Python 3.15+. Whether `name` can be an element or attribute name: one regular-expression match against the whole string |
| `xml.is_valid_text(data)` | O(n) | O(1) | Python 3.15+. Whether every character is legal in XML 1.0; the search stops at the first illegal one, so a string that fails early returns early |

## Checking Names and Text

Both checks read the string once and build nothing from it, so they are cheap enough to run on
every name or text node before it is written out.

```python
import sys

if sys.version_info >= (3, 15):
    import xml

    assert xml.is_valid_name('item-1')  # O(n)
    assert not xml.is_valid_name('1item')  # a name cannot start with a digit
    assert not xml.is_valid_name('a<b')

    assert xml.is_valid_text('tab\tand newline\n')  # O(n)
    assert not xml.is_valid_text('bell\x07')  # C0 controls other than TAB, CR and LF
```

## Version Notes

- **Python 3.15+**: `xml.is_valid_name()` and `xml.is_valid_text()`

## Related Documentation

- [html Module](html.md)
- [json Module](json.md)
