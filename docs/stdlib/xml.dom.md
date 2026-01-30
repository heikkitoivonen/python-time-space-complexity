# xml.dom Module

The `xml.dom` module defines the Document Object Model (DOM) API for XML documents. It provides interfaces used by DOM implementations like `xml.dom.minidom`.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| DOM build (via implementation) | O(n) | O(n) | Build full tree from XML input |
| `getElementsByTagName(name)` | O(n) | O(1) | Traverses the subtree to find matches |

## Common Operations (minidom)

```python
from xml.dom import minidom

# Parse XML file - O(n)
doc = minidom.parse('data.xml')

# Find elements - O(n)
items = doc.getElementsByTagName('item')
for item in items:
    print(item.firstChild.nodeValue)
```

## Related Modules

- [xml Module](xml.md) - XML package overview
- [xml.etree.ElementTree Module](xml.etree.elementtree.md) - Tree-based XML API
- [xml.sax Module](xml.sax.md) - SAX-based XML APIs
