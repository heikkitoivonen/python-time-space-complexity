# Completeness Review Prompt

You are an expert Python core contributor. You must review the documentation in the `docs/` directory to ensure it covers all public classes, methods, and functions.

## Review Criteria

- All public classes and functions are documented
- All public methods on documented classes are included
- No undocumented public API exists in covered modules

## Finding Public Classes and Functions

### For Builtin Types

List all builtin types available without imports:

```python
# Get all builtins
import builtins
public_builtins = [name for name in dir(builtins) if not name.startswith('_')]
print(public_builtins)
```

### For Standard Library Modules

Import the module and list public names:

```python
import collections

# Get all public names (classes, functions, constants)
public_names = [name for name in dir(collections) if not name.startswith('_')]
print(public_names)
```

## Finding Public Methods on Objects

Use `dir()` on the class or an instance, filtering out private/dunder methods:

```python
# List public methods
def get_public_methods(obj):
    """Return all public methods and attributes of an object."""
    return [name for name in dir(obj) if not name.startswith('_')]

# Examples
print(get_public_methods(list))    # ['append', 'clear', 'copy', 'count', ...]
print(get_public_methods(dict))    # ['clear', 'copy', 'fromkeys', 'get', ...]
print(get_public_methods(str))     # ['capitalize', 'casefold', 'center', ...]
```

### Distinguishing Methods from Attributes

```python
def get_public_methods_only(cls):
    """Return only callable methods, not data attributes."""
    return [name for name in dir(cls)
            if not name.startswith('_')
            and callable(getattr(cls, name, None))]

print(get_public_methods_only(list))
```

## Completeness Checklist

For each documented module or type:

1. **Generate the public API list**
   ```python
   public_api = get_public_methods(the_type)
   print(public_api)
   ```

2. **Compare against documentation**
   - Check that every item in `public_api` appears in the documentation
   - Flag any missing methods or functions

3. **Update documentation for gaps**
   - Add missing methods to the documentation with their complexity
   - If a method is intentionally omitted, add a comment explaining why

## Example Review Process

Reviewing `list` documentation:

```python
# Step 1: Get all public methods
list_methods = [name for name in dir(list) if not name.startswith('_')]
print(list_methods)
# Output: ['append', 'clear', 'copy', 'count', 'extend', 'index',
#          'insert', 'pop', 'remove', 'reverse', 'sort']

# Step 2: Check each against docs/builtins/list.md
documented = ['append', 'clear', 'copy', 'count', 'extend', 'index',
              'insert', 'pop', 'remove', 'reverse', 'sort']

# Step 3: Find missing
missing = set(list_methods) - set(documented)
print(f"Missing from documentation: {missing}")
```

## Output

After updating documentation, report:
1. Module or type reviewed
2. Methods/functions that were added
3. Final coverage (documented / total public API)
