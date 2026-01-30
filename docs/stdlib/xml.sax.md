# xml.sax Module

The `xml.sax` module provides a SAX (Simple API for XML) parser interface for event-driven XML processing.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `parse(file, handler)` | O(n) | O(1) | Streaming parse; memory depends on handler state |
| `parseString(xml, handler)` | O(n) | O(n) | Input string stored in memory |

## Common Operations

### Streaming Parse

```python
import xml.sax

class Handler(xml.sax.ContentHandler):
    def startElement(self, name, attrs):
        print("start", name)

    def characters(self, content):
        pass

    def endElement(self, name):
        print("end", name)

handler = Handler()
xml.sax.parse('data.xml', handler)  # O(n)
```

### Parse from a String

```python
import xml.sax

xml_data = "<root><item>A</item></root>"
handler = xml.sax.ContentHandler()
xml.sax.parseString(xml_data, handler)  # O(n)
```

## Related Modules

- [xml Module](xml.md) - XML package overview
- [xml.etree.ElementTree Module](xml.etree.elementtree.md) - Tree-based XML API
- [xml.dom Module](xml.dom.md) - DOM-based XML APIs
