# ast Module

The `ast` module provides classes for working with abstract syntax trees of Python code. It parses Python source into an AST that can be analyzed or modified.

## Complexity Reference

n is the length of the source text, N the number of nodes in a tree plus the plain entries of its list fields (a `Global`'s names are entries but not nodes), h its depth and w its widest level. A node's string fields, a `Constant`'s value or a `Name`'s identifier, have their own length, which an operation that reads, renders or compares them pays on top of the bounds below, under the same copying as the rest of its text: once in a traversal, once per ancestor in `dump()`. Every helper that recurses uses O(h) of call stack on top of what it allocates, and a tree deeper than the recursion limit raises `RecursionError`; `ast.walk()`, and `ast.increment_lineno()` built on it, use a queue instead.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.parse(source)` | O(n) | O(n) | PEG parser with memoization; `optimize=` (3.13+) also runs the AST optimizer, which folds constants on 3.13 only and replaces `__debug__` on 3.13 and later |
| `ast.literal_eval(text)` | O(n) expected | O(n) | Parses, then rebuilds the value from the tree; a dict or set of keys that collide in `hash()` is rebuilt in O(k²) for k keys. Accepts literals, containers of them, `set()` and complex sums such as `1 + 2j`; any other expression raises `ValueError`, malformed text `SyntaxError`, an unhashable key `TypeError` |
| Node construction, `ast.Name(...)` | O(1) | O(1) | Fields are set from the arguments |
| `ast.walk(node)` | O(N) | O(w) | Breadth-first through a queue never longer than two levels; the order is not promised |
| `ast.iter_child_nodes(node)` | O(k) | O(1) | k = entries across the node's fields, nodes or not; a `Global` with many names costs its names |
| `ast.iter_fields(node)` | O(f) | O(1) | f = fields on the node |
| `ast.NodeVisitor.visit(node)` | O(N) | O(h) | Each node dispatches to a `visit_<Class>` method or to `generic_visit`; the methods' own work is on top |
| `ast.NodeTransformer.visit(node)` | O(N) | O(h + N) | `generic_visit` rebuilds every list field it passes through, in place; the methods' own work is on top |
| `ast.dump(node)` | O(N * h) | O(N + h) | Each node's text is copied into its parent's, so a deep chain costs far more than a wide tree with the same nodes. `indent=` indents every line by its depth: the output becomes O(N * h) characters, which is then the space, and the copying O(N * h²) |
| `ast.unparse(node)` | O(N * (b + 1)) | O(N * (b + 1)) | b = block nesting depth: every statement line is indented by its depth, so flat code is O(N). Linear in expression depth, unlike `dump()` |
| `ast.compare(a, b)` | O(N) | O(h) | 3.14+; field-by-field, stopping at the first difference |
| `ast.copy_location(new, old)` | O(1) | O(1) | Copies the four position attributes |
| `ast.fix_missing_locations(node)` | O(N) | O(h) | Recursive |
| `ast.increment_lineno(node, n)` | O(N) | O(w) | Uses `walk()` |
| `ast.get_docstring(node)` | O(d + k * l) | O(d) | d = docstring length, l its lines, k its leading blank lines. Reads only the first statement; `clean=True` runs `inspect.cleandoc`, which pops each leading blank line from the front of the line list, `clean=False` is O(1) |
| `ast.get_source_segment(source, node)` | O(L) | O(L) | L = source length up to the node's last line (3.12+), or the whole source before 3.12; the source is split into lines on every call |
| `ast.main()` | O(n + N * h²) | O(n + N * h) | Command-line entry: parses a file and prints `dump(indent=3)` |

The `PyCF_ONLY_AST`, `PyCF_TYPE_COMMENTS`, `PyCF_ALLOW_TOP_LEVEL_AWAIT` and `PyCF_OPTIMIZED_AST` (3.13+) flags are passed to `compile()` and select what it returns; they do not change the parser's bound.

## Parsing Python Code

### Basic Parsing

```python
import ast

# Parse source code - O(n) where n = code length
code = "x = 1 + 2"
tree = ast.parse(code)

# dump() - O(N * h); this tree is four levels deep
print(ast.dump(tree))
# Module(body=[Assign(targets=[Name(id='x', ctx=Store())], value=BinOp(...))])
```

### Extracting Function Names

```python
import ast

code = """
def hello():
    pass

def world():
    pass
"""

# Parse - O(n)
tree = ast.parse(code)

# Extract functions - O(N) traversal
function_names = [
    node.name
    for node in ast.walk(tree)
    if isinstance(node, ast.FunctionDef)
]

print(function_names)  # ['hello', 'world']
```

## Safe Literal Evaluation

### Evaluate Strings Safely

```python
import ast

# Safe evaluation - O(n)
data = ast.literal_eval("{'name': 'Alice', 'age': 30}")
print(data)  # {'name': 'Alice', 'age': 30}

# Works for lists, tuples, dicts, strings, numbers
numbers = ast.literal_eval("[1, 2, 3, 4, 5]")
print(numbers)  # [1, 2, 3, 4, 5]

# Blocks arbitrary code - safe from injection
try:
    ast.literal_eval("__import__('os').system('rm -rf /')")
except ValueError:
    print("Blocked malicious code")
```

## AST Walking and Traversal

### Walking the Entire Tree

```python
import ast

code = """
x = 1
y = x + 2
z = y * 3
"""

tree = ast.parse(code)

# Walk all nodes - O(N), breadth-first: the three targets come before the
# names nested inside the expressions
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        print(f"Variable: {node.id}")

# Output:
# Variable: x
# Variable: y
# Variable: z
# Variable: x
# Variable: y
```

### Custom Node Visitor

```python
import ast

class VariableVisitor(ast.NodeVisitor):
    """Visit nodes and collect variables - O(N) time, O(h) stack"""

    def __init__(self):
        self.variables = set()

    def visit_Name(self, node):
        """Record variable names - O(1)"""
        self.variables.add(node.id)
        self.generic_visit(node)

code = "x = y + z"
tree = ast.parse(code)

visitor = VariableVisitor()
visitor.visit(tree)  # O(N) traversal
print(visitor.variables)  # {'x', 'y', 'z'}
```

### Deep Trees

```python
import ast

# A chain of 5,000 unary minuses is 5,000 levels deep; each UnaryOp
# carries an op node as well as its operand
node = ast.Constant(value=1)
for _ in range(5000):
    node = ast.UnaryOp(op=ast.USub(), operand=node)
tree = ast.Expression(body=node)

# walk() holds one level at a time - O(w) space, w = 2 here
count = sum(1 for _ in ast.walk(tree))  # 10002

# The recursive helpers need O(h) stack, and h exceeds the recursion limit
try:
    ast.NodeVisitor().visit(tree)
except RecursionError:
    print("visit() recursed past the limit")
```

## Finding Function Calls

### Extract All Function Calls

```python
import ast

code = """
result = max(1, 2, 3)
print(result)
"""

# Parse - O(n)
tree = ast.parse(code)

# Find calls - O(N) traversal
calls = [
    node.func.id
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
]

print(calls)  # ['max', 'print']
```

## Source Segments

```python
import ast

source = """
def first():
    return 1

def second():
    return 2
"""
tree = ast.parse(source)

# Each call splits the source into lines again - O(L) per call,
# O(F * L) for F functions
for node in tree.body:
    segment = ast.get_source_segment(source, node)
    print(segment.splitlines()[0])
# def first():
# def second():
```

## Version Notes

- **Python 3.11**: `TryStar` node for `except*`
- **Python 3.12**: `TypeAlias`, `TypeVar`, `ParamSpec`, `TypeVarTuple` and `type_param` nodes; `get_source_segment()` stops splitting at the node's last line
- **Python 3.13**: `ast.parse(optimize=)` and `PyCF_OPTIMIZED_AST`; `dump(show_empty=)`
- **Python 3.14**: constant folding moves from the AST optimizer to the compiler, so `optimize=` leaves `1 + 2` as a `BinOp`
- **Python 3.14**: `ast.compare()`; `TemplateStr` and `Interpolation` nodes; `Num`, `Str`, `Bytes`, `NameConstant` and `Ellipsis` removed (deprecated since 3.8)

## Related Documentation

- [inspect Module](inspect.md)
- [dis Module](dis.md)
- [compile() Function](../builtins/compile.md)
