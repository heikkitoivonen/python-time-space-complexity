# breakpoint() Function

The `breakpoint()` function drops into the Python debugger (pdb by default) for interactive debugging.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `breakpoint()` | O(1) | O(1) | Pauses execution |
| Debugger session | O(n) | O(n) | n = time spent debugging |


## Related Modules

- [pdb Module](../stdlib/pdb.md) - Python debugger
- [sys Module](../stdlib/sys.md) - System functions (breakpointhook)
- [logging Module](../stdlib/logging.md) - Production debugging
