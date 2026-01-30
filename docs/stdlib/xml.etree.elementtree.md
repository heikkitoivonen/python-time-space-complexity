# xml.etree.ElementTree Module

The `xml.etree.ElementTree` module provides a simple and efficient XML API for parsing and creating XML data.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `fromstring(xml)` | O(n) | O(n) | Parse XML string into a tree (n = input size) |
| `parse(file)` | O(n) | O(n) | Parse XML file into a tree |
| `tostring(elem)` | O(n) | O(n) | Serialize element tree to bytes/str |
| `find/findall/findtext` | O(n) typical | O(1) | Traversal over subtree |

## Common Operations

### Parse XML from a String

```python
import xml.etree.ElementTree as ET

xml = """<root><item id='1'>A</item><item id='2'>B</item></root>"""
root = ET.fromstring(xml)  # O(n)

for item in root.findall('item'):  # O(n)
    print(item.get('id'), item.text)
```

### Parse XML from a File

```python
import xml.etree.ElementTree as ET

# Parse file - O(n)
tree = ET.parse('data.xml')
root = tree.getroot()
```

### Build and Serialize XML

```python
import xml.etree.ElementTree as ET

root = ET.Element('root')
ET.SubElement(root, 'item', id='1').text = 'A'
ET.SubElement(root, 'item', id='2').text = 'B'

# Serialize - O(n)
xml_bytes = ET.tostring(root)
```

## Related Modules

- [xml Module](xml.md) - XML package overview
- [xml.dom Module](xml.dom.md) - DOM-based XML APIs
- [xml.sax Module](xml.sax.md) - SAX-based XML APIs
