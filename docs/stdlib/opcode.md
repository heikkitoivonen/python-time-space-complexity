# opcode Module

The `opcode` module provides access to Python's bytecode opcodes and their properties, useful for bytecode analysis and manipulation.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Access opcode | O(1) | O(1) | Hash lookup |
| Get opcode info | O(1) | O(1) | Static data |

## Bytecode Opcode Information

### Accessing Opcodes

```python
import opcode

# Get opcode number - O(1)
print(opcode.opmap['LOAD_CONST'])
print(opcode.opmap['RETURN_VALUE'])

# Get opcode name - O(1)
print(opcode.opname[opcode.opmap['LOAD_CONST']])

# Check if opcode has argument threshold - O(1)
print(opcode.HAVE_ARGUMENT)

# Compare opcodes - O(1)
if opcode.opmap['STORE_NAME'] > opcode.HAVE_ARGUMENT:
    print("Has argument")
```

## Related Documentation

- [dis Module](dis.md)
- [sys Module](sys.md)
