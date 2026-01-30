# stringprep Module

The `stringprep` module provides support for internationalized domain names through Unicode normalization and validation per RFC 3454.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Character mapping | O(1) | O(1) | Hash lookup |

## String Preparation

### Character Table Lookups

```python
import stringprep

# stringprep provides character table lookup functions
# Used internally by encodings.idna for domain names

# Check if character codepoint is in table - O(1)
code = ord('A')
is_mapped = stringprep.in_table_b1(code)  # O(1) - table lookup

# Check character categories - O(1) each
stringprep.in_table_c3(code)  # Private use characters
stringprep.in_table_d1(code)  # Bidi category check
```

!!! note "Low-level Module"
    stringprep is primarily used by higher-level modules like `encodings.idna`.
    For domain name preparation, use `encodings.idna.nameprep()` instead.

## Related Documentation

- [codecs Module](codecs.md)
- [encodings Module](encodings.md)
