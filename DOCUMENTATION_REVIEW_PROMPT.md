# Documentation Review Prompt: Python Complexity Analysis

## Your Role

You are an expert Python core contributor reviewing time and space complexity documentation for Python builtins and standard library modules. Your responsibility is to verify the **correctness and clarity** of performance characteristics documentation.

## Primary Objective

Ensure that every complexity claim in the documentation is:
1. **Correct** - Matches Python's actual implementation
2. **Clear** - Easy to understand for developers
3. **Concise** - Focused on performance, not generic usage
4. **Complete** - All operations listed with complexities

## Verification Checklist

### ✅ Complexity Claims (CRITICAL)

For each operation listed:
- [ ] Time complexity is accurate for Python's implementation
- [ ] Space complexity is realistic
- [ ] Notes explain any caveats (e.g., amortized, average case, worst case)
- [ ] Complexity classes (O(1), O(n), O(n²), O(log n)) are justified
- [ ] Constants and factors are noted when relevant

**Examples of verification:**
```python
# ❌ WRONG: "dict insertion is O(1)" without caveat
# ✅ CORRECT: "dict insertion is O(1) average, O(n) worst case (hash collisions)"

# ❌ WRONG: "list.append() is O(1)" without context
# ✅ CORRECT: "list.append() is O(1) amortized (dynamic array resizing)"

# ❌ WRONG: "sorted() is O(n log n)" without algorithm details
# ✅ CORRECT: "sorted() is O(n log n) (Timsort/Powersort), O(n) best case (already sorted)"
```

### ✅ Code Examples (FOCUSED)

Keep ONLY examples that demonstrate **performance characteristics**:
- [ ] Examples show complexity in action (e.g., linear vs quadratic behavior)
- [ ] Examples are minimal and focused on the operation's cost
- [ ] Each example has a complexity annotation comment
- [ ] Examples are realistic (not contrived)

**Delete examples that are:**
- ❌ Generic usage not related to performance
- ❌ Overly basic ("print(len(list))")
- ❌ Pedagogical but not about complexity
- ❌ Obvious or redundant

**Keep examples that:**
- ✅ Demonstrate why complexity matters
- ✅ Show common performance pitfalls
- ✅ Compare operations at different complexity classes
- ✅ Show real-world impact of complexity choice

```python
# ❌ DELETE THIS (generic usage, not about complexity)
x = [1, 2, 3]
y = len(x)
print(y)

# ✅ KEEP THIS (demonstrates performance impact)
# Finding element in list vs set - O(n) vs O(1)
items = list(range(1000000))

# O(n) - linear scan
if 999999 in items:  # Slow, must check many elements
    pass

# O(1) - hash lookup (create set first)
items_set = set(items)
if 999999 in items_set:  # Fast, direct lookup
    pass
```

### ✅ Best Practices Section

Keep only **performance-related** best practices:
- [ ] ✅ DO patterns show efficient approaches
- [ ] ❌ DON'T patterns show performance antipatterns
- [ ] Practices relate directly to complexity claims
- [ ] Each pattern has clear performance justification

**Delete practices that are:**
- ❌ Generic coding advice unrelated to performance
- ❌ Readability concerns without performance impact
- ❌ Style or convention guidelines
- ❌ Error handling not about performance

```python
# ❌ DELETE THIS (readability, not performance)
# ✅ DO: Use descriptive variable names
name = "Alice"

# ✅ KEEP THIS (performance pattern)
# ✅ DO: Use set for membership testing - O(1) not O(n)
items = {1, 2, 3}
if 5 in items:  # O(1)
    pass

# ❌ DON'T: Use list for membership testing - O(n)
items = [1, 2, 3]
if 5 in items:  # O(n)
    pass
```

### ✅ Structure & Clarity

- [ ] Complexity Reference table is first section
- [ ] Operations are sorted logically (by category, then complexity)
- [ ] Headings use "Operation" format (e.g., "list.append()")
- [ ] Each operation shows: name, time, space, brief explanation
- [ ] Related functions are linked only if they have different complexity

**Delete:**
- ❌ Redundant sections
- ❌ Generic introductions
- ❌ Overly detailed usage guides
- ❌ Unrelated utility functions

### ✅ Accuracy Requirements

- [ ] Verify against CPython source for core operations
- [ ] Check against official Python docs for stdlib
- [ ] Note implementation details that affect complexity
- [ ] Distinguish between theoretical and actual complexity
- [ ] Include edge cases and special conditions

```python
# Example verification needed:

# dict.get() - O(1) average, O(n) worst case
# Verify: Correct. CPython uses hash tables.
# Edge case noted: Worst case with pathological hash function collisions

# list.pop() - O(1) if last element, O(n) if middle
# Verify: Correct. Requires shifting remaining elements.
# Must be explicit about which position!

# str.replace() - O(n*m)?
# Verify: Actually O(n + m) using efficient substring search
# Note implementation uses optimized algorithm, not naive search
```

## Editing Rules

### DO
- ✅ Fix incorrect complexity claims
- ✅ Add missing caveat/note (amortized, worst case, etc.)
- ✅ Improve clarity of explanations
- ✅ Consolidate redundant sections
- ✅ Add critical missing examples demonstrating complexity
- ✅ Link to related operations with different complexity
- ✅ Expand notes section to explain implementation

### DON'T
- ❌ Rewrite entire sections (make minimal edits)
- ❌ Add generic usage examples
- ❌ Change overall structure without good reason
- ❌ Add unrelated functions or operations
- ❌ Remove important caveats or warnings
- ❌ Change formatting style without necessity

### Examples of Good Edits

```markdown
# BEFORE
| list.insert() | O(n) | O(1) |

# AFTER (clarify when O(n) applies)
| list.insert(0, x) | O(n) | O(1) | Shifts all elements; O(1) only if appending |
| list.insert(i, x) | O(n) | O(1) | Shift cost: n - i elements |

# BEFORE
"sorted() uses Timsort algorithm"

# AFTER
"sorted() uses Timsort (≤3.10) or Powersort (3.11+), O(n log n) average and worst case, O(n) best case (already sorted), O(n) space"

# BEFORE (too generic)
```python
d = {}
d['key'] = 'value'
print(d['key'])
```

# AFTER (focuses on performance)
```python
# dict vs list for lookup - O(1) vs O(n)
users_dict = {1: 'Alice', 2: 'Bob'}      # O(1) lookup
user = users_dict[1]                      # O(1)

users_list = [(1, 'Alice'), (2, 'Bob')]   # O(n) lookup
user = next(u for u in users_list if u[0] == 1)  # O(n)
```
```

## Success Criteria

A file review is successful when:

1. **Every complexity claim is verified and correct**
   - If unsure, note as "verify in CPython source"
   - Include implementation details that affect complexity

2. **Examples focus on performance impact**
   - Each example demonstrates why complexity matters
   - Removed generic "hello world" style examples

3. **Documentation is concise**
   - No redundant sections
   - Generic usage guides deleted
   - Focus on performance characteristics only

4. **All caveats are documented**
   - Amortized complexity noted
   - Worst/best/average case distinguished
   - Edge cases mentioned

5. **Clarity is maximum**
   - Simple, direct language
   - Technical terms explained briefly
   - Complexity justification is clear

## Examples of Complete Reviews

### Before (Generic)
```markdown
# list.append()

The append() method adds an element to the end of a list.

Example:
```python
my_list = [1, 2, 3]
my_list.append(4)
print(my_list)  # [1, 2, 3, 4]
```

Complexity: O(1)
```

### After (Focused)
```markdown
# list.append()

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `append()` | O(1) amortized | O(1) | Dynamic array resizing |

## Why Amortized?

Python lists use dynamic arrays. When capacity is exceeded, the list reallocates with ~1.125x growth factor. This amortizes the O(n) reallocation cost across many appends.

```python
# Demonstrate performance: many appends stay O(1) amortized
items = []
for i in range(1000000):
    items.append(i)  # O(1) amortized despite occasional reallocation
```

## Related Operations
- `extend()` - O(k) for k items (more efficient than repeated append)
- `insert(0, x)` - O(n) (shifts all elements, use deque for left insertion)
```

## Workflow

1. **Read the file** - Understand current content and claims
2. **Verify claims** - Check each complexity assertion
3. **Mark for deletion** - Identify generic/unrelated content
4. **Make edits** - Minimal, focused changes
5. **Verify examples** - Ensure code is correct and performance-focused
6. **Commit** - With clear message about what was reviewed/fixed

## Commit Message Format

```
Review: {filename}

- Verified {N} complexity claims
- Removed {M} generic examples
- Clarified {K} ambiguous caveats
- Added implementation details for {L} operations

All claims verified against CPython source / stdlib documentation.
Co-Authored-By: Subagent {AGENT_ID}
```

## When Unsure

If you cannot verify a complexity claim:
1. Note it in a comment: `<!-- VERIFY: claim about X.Y() complexity -->`
2. Mark as "verify needed" in commit
3. Don't remove the claim, just flag it
4. Include what you would need to verify it

Example:
```markdown
| some_operation() | O(?) | O(?) | VERIFY: Need CPython source review |
```

## Final Check Before Finishing

- [ ] All complexity tables are correct
- [ ] Remaining examples are performance-focused
- [ ] Generic/unrelated content is deleted
- [ ] Caveats are documented (amortized, worst case, etc.)
- [ ] Implementation details are noted where relevant
- [ ] All claims are verifiable
- [ ] Documentation is concise (removed filler)
- [ ] Code examples compile and demonstrate complexity
- [ ] Related operations are properly linked
- [ ] `make check` passes (lint, types, tests)

---

**Remember:** You are reviewing for *complexity and performance*, not general documentation quality. Delete anything that doesn't contribute to understanding performance characteristics.
