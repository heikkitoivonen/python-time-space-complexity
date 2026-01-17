# ast Module

The `ast` module provides classes for working with abstract syntax trees of Python code. It parses Python source into an AST that can be analyzed or modified.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.parse()` | O(n) | O(n) | n = source code length |
| `ast.literal_eval()` | O(n) | O(n) | Safe evaluation of literals |
| Tree traversal | O(n) | O(h) | n = nodes, h = max recursion depth |
| Node creation | O(1) | O(1) | Create single node |

## Parsing Python Code

### Basic Parsing

```python
import ast

# Parse source code - O(n) where n = code length
code = "x = 1 + 2"
tree = ast.parse(code)

# Tree structure - O(1) to access
print(ast.dump(tree))
# Module(body=[Assign(targets=[Name(id='x')], value=BinOp(...))])
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

# Extract functions - O(n) traversal
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

# Walk all nodes - O(n) where n = total nodes
for node in ast.walk(tree):
    if isinstance(node, ast.Name):
        print(f"Variable: {node.id}")

# Output:
# Variable: x
# Variable: x
# Variable: y
# Variable: y
# Variable: z
```

### Custom Node Visitor

```python
import ast

class VariableVisitor(ast.NodeVisitor):
    """Visit nodes and collect variables - O(n)"""
    
    def __init__(self):
        self.variables = set()
    
    def visit_Name(self, node):
        """Record variable names - O(1)"""
        self.variables.add(node.id)
        self.generic_visit(node)

code = "x = y + z"
tree = ast.parse(code)

visitor = VariableVisitor()
visitor.visit(tree)  # O(n) traversal
print(visitor.variables)  # {'x', 'y', 'z'}
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

# Find calls - O(n) traversal
calls = [
    node.func.id
    for node in ast.walk(tree)
    if isinstance(node, ast.Call) 
    and isinstance(node.func, ast.Name)
]

print(calls)  # ['max', 'print']
```

## Related Documentation

- [inspect Module](inspect.md)
- [dis Module](dis.md)
- [compile() Function](../builtins/index.md)
