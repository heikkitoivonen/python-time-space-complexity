# pyexpat Module

The `pyexpat` module provides a low-level interface to the Expat XML parser.
Most users should prefer `xml.etree.ElementTree` or `xml.sax` for higher-level APIs.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ParserCreate()` | O(1) | O(1) | Create a parser instance |
| `parser.Parse(data, isfinal)` | O(n) | O(d) | n = input size, d = max element nesting |

## Basic Parsing

```python
import pyexpat

def start(name, attrs):
    print("start", name, attrs)

def end(name):
    print("end", name)

parser = pyexpat.ParserCreate()
parser.StartElementHandler = start
parser.EndElementHandler = end

xml = "<root><item id='1'/></root>"
parser.Parse(xml, True)
```

## Notes

- `parser.Parse` may raise `pyexpat.ExpatError` on malformed XML.
- The parser is streaming; it does not build a tree unless you do so in handlers.

## Related Modules

- [xml.etree.ElementTree Module](xml.etree.elementtree.md)
- [xml.sax Module](xml.sax.md)
- [xml.dom Module](xml.dom.md)
