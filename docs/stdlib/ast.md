# ast Module Complexity

The `ast` module turns Python source into a tree of node objects and turns such a tree back
into source. `parse()` is a thin wrapper over `compile()` with the `PyCF_ONLY_AST` flag, so the
parsing itself is C; everything else in the module - the traversal helpers, the visitors,
`dump()` and `unparse()` - is Python working one node at a time. Nothing here streams: the whole
tree is built before any helper runs on it.

The unit of work is the node. Nodes are plain objects whose fields are ordinary attributes, so
building one, reading a field and testing its class are all O(1); what costs is how many nodes an
operation touches and how deep it has to go to reach them.

`n` is the length of the source text, `N` the number of nodes in a tree plus the plain entries of
its list fields (a `Global`'s names are entries but not nodes), `h` its depth, `w` its widest
level, `s` the statements in it and `b` the deepest block nesting. `k` is the entries across one
node's fields and `f` its fields. Terms local to one row are defined in its Notes.

A node's text - a `Constant`'s string value, a `Name`'s identifier - has its own length, which an
operation that reads, renders or compares it pays on top of the bounds below, under the same
copying as the rest of the node's text: once in a traversal, once per ancestor in `dump()`, once
per enclosing interpolation in `unparse()`. A `Constant` holding anything else costs whatever that
value's own operations cost. Every helper that recurses uses O(h) of call stack on top of what it
allocates, and a tree deeper than the recursion limit raises `RecursionError`; `ast.walk()`, and
`ast.increment_lineno()` built on it, use a queue instead.

## Complexity Reference

### Parsing and evaluating

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.parse(source, filename, mode, *, type_comments=False, feature_version=None, optimize=-1)` | O(n) | O(n) | PEG parser with memoization; `optimize=` (3.13+) also runs the AST optimizer, which folds constants on 3.13 only and replaces `__debug__` on 3.13 and later |
| `ast.literal_eval(node_or_string)` | O(N) expected, plus O(n) for a string | O(N), plus O(n) for a string | A string is parsed first, a tree is not. Rebuilds the value by recursing over the tree, so nesting costs stack; a dict or set of c keys that collide in `hash()` is rebuilt in O(c²). Accepts literals, containers of them, `set()` and complex sums such as `1 + 2j`; any other expression raises `ValueError`, malformed text `SyntaxError`, an unhashable key `TypeError` |
| `ast.main(args=None)` | O(n + N * h²) | O(n + N * h) | Command-line entry: reads a file and prints `dump(indent=3)` |
| `ast.PyCF_ONLY_AST`, `ast.PyCF_TYPE_COMMENTS`, `ast.PyCF_ALLOW_TOP_LEVEL_AWAIT`, `ast.PyCF_OPTIMIZED_AST` | O(1) | O(1) | Integer flags read off the module and passed to `compile()`; they select what it returns, not how long it takes. `ast.PyCF_OPTIMIZED_AST` is 3.13+ |

### AST

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.AST` | O(1) | O(1) | Base class of every node; it carries no fields of its own |
| `ast.Name(id='x', ctx=ast.Load())`, and every other node constructor bar `ast.ExtSlice` | O(1) | O(1) | Each field is stored from its argument and a list field is kept, not copied; the grammar fixes how many fields a class has. From 3.13 an omitted field is filled from a class default - a fresh empty list for a list field, the shared `Load()` for `ctx` - and omitting a required one warns |
| `node.id`, `node.body`, any field | O(1) | O(1) | Ordinary instance attributes; reading a list field hands back the list itself |
| `ast.AST._fields`, `ast.AST._attributes` | O(1) | O(1) | The class's own tuples, shared by every instance of it |
| `ast.AST._field_types` | O(1) | O(1) | 3.13+; the class's field annotations, which is how `dump()` knows whether an empty value belongs to a list field it may omit |
| `ast.AST.lineno`, `ast.AST.col_offset`, `ast.AST.end_lineno`, `ast.AST.end_col_offset` | O(1) | O(1) | Positions, listed in `_attributes` rather than `_fields`, and only on the classes whose `_attributes` names them - an operator class such as `ast.Add` has none. The parser sets them; a hand-built node has what its constructor was given. `copy_location()` takes what another node has - a start position the source lacks is left alone, an end position is copied even when it is `None` - and `fix_missing_locations()` fills in what is missing from each node's parent |
| `FunctionDef.type_comment`, `AsyncFunctionDef.type_comment`, `Assign.type_comment`, `For.type_comment`, `AsyncFor.type_comment`, `With.type_comment`, `AsyncWith.type_comment`, `arg.type_comment` | O(1) | O(1) | Filled only when `parse(type_comments=True)` asks the parser to collect them; otherwise `None` |

### Node classes

Every node class is a plain constructor over its own fields, so the rows below share one bound -
the deprecated `ast.ExtSlice` is the one exception. What differs between the rest is how many
fields the grammar gives each class, and that is a constant.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.Module`, `ast.Interactive`, `ast.Expression`, `ast.FunctionType` | O(1) | O(1) | The `ast.mod` roots, one per `parse()` mode |
| `ast.FunctionDef`, `ast.AsyncFunctionDef`, `ast.ClassDef`, `ast.Return`, `ast.Delete`, `ast.Assign`, `ast.AugAssign`, `ast.AnnAssign`, `ast.For`, `ast.AsyncFor`, `ast.While`, `ast.If`, `ast.With`, `ast.AsyncWith`, `ast.Match`, `ast.Raise`, `ast.Try`, `ast.TryStar`, `ast.Assert`, `ast.Import`, `ast.ImportFrom`, `ast.Global`, `ast.Nonlocal`, `ast.Expr`, `ast.Pass`, `ast.Break`, `ast.Continue`, `ast.TypeAlias` | O(1) | O(1) | The `ast.stmt` classes. Each one starts a line of its own in `unparse()`, indented by its block depth - the `s * b` term there |
| `ast.BoolOp`, `ast.NamedExpr`, `ast.BinOp`, `ast.UnaryOp`, `ast.Lambda`, `ast.IfExp`, `ast.Dict`, `ast.Set`, `ast.ListComp`, `ast.SetComp`, `ast.DictComp`, `ast.GeneratorExp`, `ast.Await`, `ast.Yield`, `ast.YieldFrom`, `ast.Compare`, `ast.Call`, `ast.FormattedValue`, `ast.JoinedStr`, `ast.TemplateStr`, `ast.Interpolation`, `ast.Constant`, `ast.Attribute`, `ast.Subscript`, `ast.Starred`, `ast.Name`, `ast.List`, `ast.Tuple`, `ast.Slice` | O(1) | O(1) | The `ast.expr` classes. `ast.TemplateStr` and `ast.Interpolation` are 3.14+ |
| `ast.Load`, `ast.Store`, `ast.Del` | O(1) | O(1) | The `ast.expr_context` markers on a `Name`, `Attribute`, `Subscript`, `Starred`, `List` or `Tuple` |
| `ast.And`, `ast.Or`; `ast.Add`, `ast.Sub`, `ast.Mult`, `ast.MatMult`, `ast.Div`, `ast.Mod`, `ast.Pow`, `ast.LShift`, `ast.RShift`, `ast.BitOr`, `ast.BitXor`, `ast.BitAnd`, `ast.FloorDiv`; `ast.Invert`, `ast.Not`, `ast.UAdd`, `ast.USub`; `ast.Eq`, `ast.NotEq`, `ast.Lt`, `ast.LtE`, `ast.Gt`, `ast.GtE`, `ast.Is`, `ast.IsNot`, `ast.In`, `ast.NotIn` | O(1) | O(1) | The fieldless operator classes - `ast.boolop`, `ast.operator`, `ast.unaryop` and `ast.cmpop`. Each is still a node, so it counts towards N in a traversal |
| `ast.arguments`, `ast.arg`, `ast.keyword`, `ast.alias`, `ast.withitem`, `ast.comprehension`, `ast.ExceptHandler`, `ast.match_case`, `ast.TypeIgnore` | O(1) | O(1) | The helper nodes hanging off a statement |
| `ast.MatchValue`, `ast.MatchSingleton`, `ast.MatchSequence`, `ast.MatchMapping`, `ast.MatchClass`, `ast.MatchStar`, `ast.MatchAs`, `ast.MatchOr` | O(1) | O(1) | The `ast.pattern` classes under a `match_case` |
| `ast.TypeVar`, `ast.ParamSpec`, `ast.TypeVarTuple` | O(1) | O(1) | 3.12+; the `ast.type_param` classes on a `FunctionDef`, `ClassDef` or `TypeAlias` |
| `ast.mod`, `ast.stmt`, `ast.expr`, `ast.expr_context`, `ast.boolop`, `ast.operator`, `ast.unaryop`, `ast.cmpop`, `ast.pattern`, `ast.excepthandler`, `ast.type_ignore`, `ast.type_param` | O(1) | O(1) | The abstract groups. One `isinstance()` against a group selects a whole grammar category without listing its classes |
| `ast.slice`, `ast.Index`, `ast.Suite`, `ast.AugLoad`, `ast.AugStore`, `ast.Param` | O(1) | O(1) | Deprecated and unused; `ast.Index(value)` returns `value` itself rather than a node |
| `ast.ExtSlice(dims)` | O(k) | O(k) | Deprecated; returns an `ast.Tuple` holding a copy of the k dims |

### Traversal

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.walk(node)` | O(N) | O(w) | Breadth-first through a queue never longer than two levels; the order is not promised |
| `ast.iter_child_nodes(node)` | O(k) | O(1) | k = entries across the node's fields, nodes or not; a `Global` with many names costs its names |
| `ast.iter_fields(node)` | O(f) | O(1) | f = fields on the node |
| `ast.NodeVisitor.visit(node)` | O(N) | O(h) | Each node dispatches to a `visit_<Class>` method or to `generic_visit`; the methods' own work is on top |
| `ast.NodeVisitor.generic_visit(node)` | O(N) | O(h) | The default: visit each child, so it walks the whole subtree. A `visit_<Class>` that does not call it stops the descent there |
| `ast.NodeTransformer.visit(node)` | O(N) | O(h + N) | The methods' own work is on top |
| `ast.NodeTransformer.generic_visit(node)` | O(N) | O(h + N) | Collects each list field's survivors into a new list and assigns it back with a slice, so the field keeps its list object |

### Rendering

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.dump(node, annotate_fields=True, include_attributes=False, *, indent=None, show_empty=False)` | O(N * h) | O(N + h) | Each node's text is copied into its parent's, so a deep chain costs far more than a wide tree with the same nodes. `indent=` indents every line by its depth: the output becomes O(N * h) characters, which is then the space, and the copying O(N * h²) |
| `ast.unparse(node)` | O(N * (q + 1) + s * b) | O(N + s * b) | Only statements are indented, each by its own block depth, so ordinary expression depth costs nothing and flat code is O(N) - linear in a depth `dump()` charges for. A `FormattedValue`, and an `Interpolation` with no recorded source text, renders its expression with a fresh unparser and copies the result into the enclosing string; q is how deeply those renderings nest, and text under q of them is copied q times. The copies are made one after another, so only the output is held |

### Comparing and locating

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.compare(a, b, /, *, compare_attributes=False)` | O(N) | O(h) | 3.14+; field by field, stopping at the first difference. `compare_attributes=True` adds the positions, so two structurally equal trees can then compare unequal because they sat at different places in their source |
| `ast.copy_location(new, old)` | O(1) | O(1) | Copies the four position attributes |
| `ast.fix_missing_locations(node)` | O(N) | O(h) | Recursive; each node inherits its parent's position where its own is missing |
| `ast.increment_lineno(node, n=1)` | O(N) | O(w) | Uses `walk()` |

### Source text

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ast.get_docstring(node, clean=True)` | O(d + p * l) | O(d) | d = docstring length, l its lines, p its leading blank lines. Reads only the first statement; `clean=True` runs `inspect.cleandoc`, which pops each leading blank line from the front of the line list, `clean=False` is O(1) |
| `ast.get_source_segment(source, node, *, padded=False)` | O(L) | O(L) | L = source length up to the node's last line (3.12+), or the whole source before 3.12; the source is split into lines on every call |

## Parsing Python Code

### Basic Parsing

```python
import ast

# Parse source code - O(n) where n = code length
code = "x = 1 + 2"
tree = ast.parse(code)

# dump() - O(N * h); this tree is four levels deep
text = ast.dump(tree)

# Before 3.13 the empty `type_ignores` field is printed too
assert text.startswith(
    "Module(body=[Assign(targets=[Name(id='x', ctx=Store())], "
    "value=BinOp(left=Constant(value=1), op=Add(), right=Constant(value=2)))]"
)
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

assert function_names == ["hello", "world"]
```

## Node Classes

Every class in the grammar is a container over a fixed set of fields, so constructing one and
reading a field are O(1). The abstract groups - `ast.stmt`, `ast.expr`, `ast.operator` and the
rest - let a traversal select a whole category with one `isinstance()` instead of a tuple of
concrete classes.

```python
import ast

tree = ast.parse("total = 0\nfor i in range(3):\n    total += i\n")

# One isinstance per node - O(N) for the walk, O(1) per test
statements = [node for node in ast.walk(tree) if isinstance(node, ast.stmt)]
operators = [node for node in ast.walk(tree) if isinstance(node, ast.operator)]

assert [type(node).__name__ for node in statements] == ["Assign", "For", "AugAssign"]
assert len(operators) == 1 and isinstance(operators[0], ast.Add)

# A list field is kept, not copied, so the constructor stays O(1)
body = [ast.Pass()]
assert ast.Module(body=body, type_ignores=[]).body is body
assert ast.Module._fields == ("body", "type_ignores")
assert ast.Name._attributes == ("lineno", "col_offset", "end_lineno", "end_col_offset")
```

### Building a Tree by Hand

`compile()` needs `lineno` and `col_offset` on every node that has them in `_attributes`; the end
positions are optional. Supplying what a hand-built tree is missing is one more O(N) pass rather
than something the constructors do.

```python
import ast

# O(1) per node; passing every field keeps the tree valid on 3.10 as well
call = ast.Call(
    func=ast.Name(id="print", ctx=ast.Load()),
    args=[ast.Constant(value="hi", kind=None)],
    keywords=[],
)
tree = ast.Module(body=[ast.Expr(value=call)], type_ignores=[])

ast.fix_missing_locations(tree)  # O(N) time, O(h) stack

assert ast.unparse(tree) == "print('hi')"
assert compile(tree, "<generated>", "exec").co_name == "<module>"
```

## Safe Literal Evaluation

```python
import ast

# Safe evaluation - O(n)
data = ast.literal_eval("{'name': 'Alice', 'age': 30}")
assert data == {"name": "Alice", "age": 30}

# Works for lists, tuples, dicts, strings, numbers
numbers = ast.literal_eval("[1, 2, 3, 4, 5]")
assert numbers == [1, 2, 3, 4, 5]

# Blocks arbitrary code - safe from injection
try:
    ast.literal_eval("__import__('os').system('rm -rf /')")
except ValueError:
    pass
else:
    raise AssertionError("a call should not be evaluated")
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
names = [node.id for node in ast.walk(tree) if isinstance(node, ast.Name)]

assert names == ["x", "y", "z", "x", "y"]
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

assert visitor.variables == {"x", "y", "z"}
```

### Deep Trees

```python
import ast

# A chain of 5,000 unary minuses is 5,000 levels deep; each UnaryOp
# carries an op node as well as its operand
node = ast.Constant(value=1, kind=None)
for _ in range(5000):
    node = ast.UnaryOp(op=ast.USub(), operand=node)
tree = ast.Expression(body=node)

# walk() holds one level at a time - O(w) space, w = 2 here
assert sum(1 for _ in ast.walk(tree)) == 10002

# The recursive helpers need O(h) stack, and h exceeds the recursion limit
try:
    ast.NodeVisitor().visit(tree)
except RecursionError:
    pass
else:
    raise AssertionError("visit() should have recursed past the limit")
```

## Finding Function Calls

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

assert calls == ["max", "print"]
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
firsts = [ast.get_source_segment(source, node).splitlines()[0] for node in tree.body]

assert firsts == ["def first():", "def second():"]
```

## Common Patterns

### Rewriting a Tree and Reading It Back

`NodeTransformer` replaces nodes as it descends, and `unparse()` turns the result back into
source. The transformer's own traversal is O(N) plus whatever the visitor methods do, and the
unparse is O(N) for flat code like this. Calling `generic_visit()` first is what makes the rewrite
bottom-up, so a folded child is already in place when its parent is examined.

```python
import ast

class FoldIntegerSums(ast.NodeTransformer):
    """Fold `int + int` - O(N) over the tree, O(h) stack, plus each addition"""

    def visit_BinOp(self, node):
        self.generic_visit(node)  # children first, so nested sums fold too
        if (
            isinstance(node.op, ast.Add)
            and isinstance(node.left, ast.Constant)
            and isinstance(node.right, ast.Constant)
            and isinstance(node.left.value, int)
            and isinstance(node.right.value, int)
        ):
            folded = ast.Constant(value=node.left.value + node.right.value, kind=None)
            return ast.copy_location(folded, node)  # O(1)
        return node

tree = ast.parse("x = 1 + 2 + 3")
folded = FoldIntegerSums().visit(tree)

assert ast.unparse(folded) == "x = 6"  # O(N) here: no blocks, no f-strings
```

### Collecting Imports in One Pass

One `walk()` answers several questions about a tree; a second walk costs another O(N).

```python
import ast

tree = ast.parse("import os, sys\nfrom pathlib import Path\n")

modules = []
for node in ast.walk(tree):  # O(N)
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom):
        modules.append(node.module)

assert modules == ["os", "sys", "pathlib"]
```

## Performance Best Practices

✅ **Do**:

- Collect everything one pass needs from a single `walk()`, rather than walking once per question
- Use `walk()` on a tree that may be deep: it queues instead of recursing, so depth costs O(w)
  memory rather than stack
- Keep `dump()` for small trees, and reach for `unparse()` on a deep one - it is linear in the
  depth that `dump()` charges for a second time through repeated copying. Both still recurse, so
  neither one survives a tree deeper than the recursion limit
- Pass a parsed tree to `literal_eval()` when you already have one; it only parses a string

❌ **Avoid**:

- `dump(indent=...)` on a deeply nested tree - the indentation alone makes the output O(N * h)
  characters and the copying O(N * h²)
- Reading `unparse()` as linear through nested f-strings: each level re-renders and copies what is
  inside it
- Calling `get_source_segment()` once per node: each call re-splits the source, so F nodes cost
  O(F * L)
- `NodeVisitor` or `NodeTransformer` on machine-generated trees of unknown depth, unless you
  have raised the recursion limit
- Rebuilding a tree to change line numbers - `increment_lineno()` does it in one queued pass

## Version Notes

- **Python 3.11+**: `TryStar` node for `except*`
- **Python 3.12+**: `TypeAlias`, `TypeVar`, `ParamSpec`, `TypeVarTuple` and `type_param` nodes;
  `get_source_segment()` stops splitting at the node's last line; `unparse()` can nest f-strings
  freely, where 3.10 and 3.11 run out of quote characters: four levels round-trip, the fifth emits
  text the parser rejects, and the sixth raises `ValueError`
- **Python 3.13+**: `ast.parse(optimize=)` and `PyCF_OPTIMIZED_AST`; `dump(show_empty=)`, and
  with it a default that omits an empty list field rather than printing it;
  `_field_types`; node constructors fill an omitted optional field from a class default, and
  omitting a required one is a `DeprecationWarning` that becomes an error in 3.15
- **Python 3.14+**: `ast.compare()`; `TemplateStr` and `Interpolation` nodes; constant folding
  moves from the AST optimizer to the compiler, so `optimize=` leaves `1 + 2` as a `BinOp`;
  `Num`, `Str`, `Bytes`, `NameConstant` and `Ellipsis` removed (deprecated since 3.8), and with
  them `NodeVisitor.visit_Constant`, the shim that forwarded to their visitor methods
- **All Python 3**: two syntactic caps bound what the parser accepts - parentheses at 200 levels
  and indentation at 99, so `b` in a parsed tree is at most 99. Nesting that needs neither, such as
  a chain of unary minuses, is bounded instead by the parser's own stack, thousands of levels
  further out; a tree built by hand meets none of the three

## Related Modules

- **[inspect](inspect.md)** - `cleandoc()`, the O(d + p * l) step inside `get_docstring()`
- **[dis](dis.md)** - the other end of the pipeline, once a tree has been compiled
- **[compile()](../builtins/compile.md)** - what `parse()` calls, and what takes a tree back
