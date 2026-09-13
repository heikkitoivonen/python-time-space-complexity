# annotationlib Module Complexity

The `annotationlib` module introspects annotations, which Python 3.14 no
longer evaluates when a function, class or module is defined (PEP 649). Its
cost is governed by the `Format` you ask for. On a function, class or
module whose annotations the compiler deferred, `VALUE` evaluates the
annotation expressions once, caches the result on the object, and copies it
on each call. `FORWARDREF` uses that cache when every name resolves and
otherwise re-runs the `__annotate__` function under a substitute namespace
on every call. `STRING` re-runs it on every call, whether or not the names
resolve, so once the annotations are cached it is the one format still
doing more than a copy.

## Complexity Reference

Let `n` be the number of annotations on the object, `e` the total length
of their expressions' source text, `g` the number of names in the owning
module's globals plus builtins, `m` the number of names in the owner class's
namespace, `l` the number in a `locals` argument, and `r` the total length
of the text produced. The bounds count the module's own work: whatever the
expressions themselves compute, and any `__repr__` they reach, adds its own
cost. Terms linear in the number of type parameters, closure cells and
`__wrapped__` layers an evaluation consults are omitted; they are a
handful of names.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Format`, `Format.VALUE`, `Format.FORWARDREF`, `Format.STRING` | O(1) | O(1) | `IntEnum` members. `Format.VALUE_WITH_FAKE_GLOBALS` is internal; `get_annotations()` and `call_annotate_function()` reject it with `ValueError` |
| `get_annotations(obj)` with `format=Format.VALUE` | O(n) | O(n) | Copies the object's cached `__annotations__`. The first access evaluates the expressions, O(e), and raises `NameError` for an undefined name; after that they are never evaluated again |
| `get_annotations(obj, format=Format.FORWARDREF)` | as `VALUE` when every name resolves, O(e + g) otherwise | as `VALUE`, O(e + g) otherwise | Evaluates, caches and copies like `VALUE` when the expressions evaluate. Otherwise every call attempts the evaluation, then re-runs `__annotate__` over a merged copy of the globals, with each unresolved name as a `ForwardRef`; nothing is cached |
| `get_annotations(obj, format=Format.STRING)` | O(e) | O(e) | Runs `__annotate__` under a namespace that records every operation, then unparses each result. From 3.14.1 it first runs `__annotate__` under the real globals as well, so the calls inside the annotations run on every `STRING` call, up to the first annotation that raises. Nothing is cached. An object with `__annotations__` but no `__annotate__`, such as a class whose annotations were assigned directly, is converted with `annotations_to_string()` instead, O(n + r) |
| `get_annotations(obj, eval_str=True)` | O(n + e + m + l) | O(n + e + m + l) | Compiles and evaluates each string value with `eval()` on every call. A class owner's namespace is copied for `locals` unless both `globals` and `locals` are given, and a given `locals` is copied when the object has type parameters. Only with `format=Format.VALUE` |
| `call_annotate_function(annotate, format)` | O(e) for `VALUE` and `STRING`, O(e + g) for `FORWARDREF` | O(e), O(e + g) for `FORWARDREF` | The uncached path behind `get_annotations()`. With a compiler-generated `annotate`, `FORWARDREF` merges the builtins and globals into its substitute namespace on every call, whether or not a name is unresolved |
| `call_evaluate_function(evaluate, format)` | as `call_annotate_function()` | as `call_annotate_function()` | `evaluate` is a type alias's `evaluate_value` or a type parameter's `evaluate_bound`, `evaluate_constraints` or `evaluate_default`; returns one value, not a dict |
| `get_annotate_from_class_namespace(namespace)` | O(1) | O(1) | Two dict lookups, `__annotate__` then `__annotate_func__`; returns the function or `None` |
| `annotations_to_string(annotations)` | O(n + r) | O(n + r) | New dict with `type_repr()` of each non-string value; string values pass through unchanged |
| `type_repr(value)` | O(r) | O(r) | Qualified name for a class or function, `...` for `Ellipsis`, the source of a template string, `repr()` otherwise |
| `ForwardRef(arg)` | O(1) | O(1) | Stores the string. An expression other than a bare name is compiled on the first `evaluate()` and the code cached on the reference |
| `ForwardRef.evaluate()` | O(e + m + l), O(e + m + l + g) for a `FORWARDREF` retry | O(e + m + l), O(e + m + l + g) for a `FORWARDREF` retry | A bare name is a lookup in `locals`, `globals` then builtins; any other expression is an `eval()` of the cached code. With a class owner and no `locals`, the class namespace is copied first, O(m); a given `locals` may be copied, and is merged into a retry, O(l). `format=Format.STRING` returns the source text. `format=Format.FORWARDREF` returns the reference itself for an unresolved bare name; any other expression that fails is retried over a merged copy of the globals and `locals`, and the result carries each unresolved name as a `ForwardRef`, or is the reference itself when the retry fails too |

## Evaluation Is Deferred, Then Cached

Defining a class does not evaluate its annotations. The first `VALUE`
access does, once; every later call copies the cached dict.

```python
from annotationlib import get_annotations

evaluations = 0

def expensive():
    global evaluations
    evaluations += 1  # runs when the annotation is evaluated, not when defined
    return int

class Config:
    port: expensive()

assert evaluations == 0  # O(1): defining the class evaluated nothing

first = get_annotations(Config)  # O(e): evaluates and caches
assert evaluations == 1

second = get_annotations(Config)  # O(n): copies the cache
assert evaluations == 1
assert first is not second and first["port"] is second["port"]
```

## Choosing a Format

The formats differ in what they return for an undefined name and in what
they cost per call.

```python
from annotationlib import Format, ForwardRef, get_annotations

def handler(request: Request, retries: int) -> None:
    pass

# VALUE raises on the first evaluation: Request is not defined
try:
    get_annotations(handler)
except NameError:
    pass

# FORWARDREF re-runs __annotate__ on every call, O(e + g), and wraps
# the unresolved name; a resolved one is the real object
refs = get_annotations(handler, format=Format.FORWARDREF)
assert isinstance(refs["request"], ForwardRef)
assert refs["retries"] is int

# STRING re-runs __annotate__ on every call, O(e), and unparses the source
strings = get_annotations(handler, format=Format.STRING)
assert strings == {"request": "Request", "retries": "int", "return": "None"}
```

When every name resolves, `VALUE` and `FORWARDREF` both copy the cache in
O(n), while `STRING` still re-runs and unparses the expressions on every
call. Use `STRING` for display, and cache its result yourself if it is
needed repeatedly.

## Evaluating a Forward Reference

`ForwardRef.evaluate()` resolves a name against the `locals` given, else
the owner's namespace, then the globals and builtins. With a class owner
and no `locals`, the whole class namespace is copied on every call.

```python
from annotationlib import Format, ForwardRef

class Model:
    Id = int

ref = ForwardRef("Id", owner=Model)

assert ref.evaluate() is int  # O(e + m): copies Model's namespace, then looks up
assert ref.evaluate(locals={"Id": str}) is str  # O(e + l): the given locals, copied
assert ref.evaluate(format=Format.STRING) == "Id"  # O(1): the source text

unresolved = ForwardRef("Missing")
assert unresolved.evaluate(format=Format.FORWARDREF) is unresolved

partial = ForwardRef("list[Missing]").evaluate(format=Format.FORWARDREF)  # O(e + g)
assert str(partial) == "list[ForwardRef('Missing')]"
```

## Evaluate Functions

A `type` alias and a type parameter's bound, constraints and default are
also evaluated lazily. `call_evaluate_function()` applies a `Format` to one
of those expressions and returns a single value.

```python
from annotationlib import Format, call_evaluate_function

type Rows = list[Row]

# STRING: the source text, O(e), without defining Row
assert call_evaluate_function(Rows.evaluate_value, Format.STRING) == "list[Row]"

# FORWARDREF: the real list with Row wrapped, O(e + g)
partial = call_evaluate_function(Rows.evaluate_value, Format.FORWARDREF)
assert str(partial) == "list[ForwardRef('Row')]"
```

## Version Notes

- **Python 3.14+**: Module introduced (PEP 749)
- **Python 3.14+**: Deferred annotation evaluation default (PEP 649)

## Related Documentation

- [Typing Module](typing.md)
- [Inspect Module](inspect.md)
- [Python 3.14](../versions/py314.md)
