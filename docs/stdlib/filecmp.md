# filecmp Module Complexity

The `filecmp` module compares files and directory trees in pure Python. A file comparison starts
with two `os.stat` calls and reads the contents only when the stat signatures cannot decide it; a
directory comparison lists, stats and compares nothing until you read one of its attributes.

`n` is the size of one file in bytes, `s` is the bytes the content comparisons read (zero when
every pair is decided by its stat signature), `f` is the names passed to `cmpfiles()`, `e` is the
entries in the two listings of one directory pair, and `t` is the entries listed across every
directory pair a call visits. Each `os.stat` call and each listed entry is priced at O(1), and the
`ignore` and `hide` lists are treated as short: every listed name is checked against them by a
list scan.

## Complexity Reference

### Comparing files

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `filecmp.cmp(f1, f2, shallow=True)` | O(n) | O(1) | O(1) with no read when either path is not a regular file, the sizes differ, or `shallow` is true and the signatures (type, size, mtime) match; otherwise both files are read block by block up to the first block that differs |
| Repeating a `cmp()` whose files have not changed | O(1) | O(1) | Cached under both paths and both signatures until the cache fills, at about a hundred results, and is emptied; a rewrite that keeps the size and mtime is not seen |
| `filecmp.cmpfiles(a, b, common, shallow=True)` | O(f + s) | O(f) | One `cmp()` per name; a name missing on either side goes to the third list |
| `filecmp.clear_cache()` | O(1) | O(1) | Bounded by the cache's fixed maximum; needed after a rewrite that kept the size and mtime |

### dircmp

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `filecmp.dircmp(a, b, ignore=None, hide=None, *, shallow=True)` | O(1) | O(1) | Nothing is listed or stat'ed yet; `shallow` is Python 3.13+ |
| `dircmp.left`, `dircmp.right` | O(1) | O(1) | The two paths as given |
| `dircmp.left_list`, `dircmp.right_list` | O(e log e) | O(e) | Lists and sorts both directories, filtered by `hide` and `ignore` |
| `dircmp.common`, `dircmp.left_only`, `dircmp.right_only` | O(e log e) | O(e) | Computed together from the listing |
| `dircmp.common_dirs`, `dircmp.common_files`, `dircmp.common_funny` | O(e log e) | O(e) | Adds two `os.stat` calls per common name |
| `dircmp.same_files`, `dircmp.diff_files`, `dircmp.funny_files` | O(e log e + s) | O(e) | Adds one `cmp()` per common file, with this object's `shallow` |
| `dircmp.subdirs` | O(e log e) | O(e) | One new `dircmp` of the same class per common subdirectory; none of them lists anything yet |
| `dircmp.report()` | O(e log e + s) | O(e) | Prints this directory pair only; `subdirs` is never touched |
| `dircmp.report_partial_closure()` | O(t log t + s) | O(t) | This pair and each immediate common subdirectory pair |
| `dircmp.report_full_closure()` | O(t log t + s) | O(t) | Every pair in the common tree, each kept in its parent's `subdirs`; a directory on one side only is not entered |
| `filecmp.DEFAULT_IGNORES` | O(1) | O(1) | The names skipped when `ignore` is omitted |
| `python -m filecmp [-r] dir1 dir2` | O(t log t + s) | O(t) | `report()`, or `report_full_closure()` with `-r`; always shallow |

Each `dircmp` attribute is computed on first access, together with the attributes it depends on,
and stored: every later access is O(1). The bounds above include that dependency chain, so
`same_files` on a fresh object lists, stats and compares.

## Comparing Files

### Shallow Comparison

`shallow=True` does not mean the contents are never read. It means that two files with the same
type, size and mtime are taken to be equal without reading them. When the sizes match but the
mtimes do not - a copy made without preserving timestamps, say - the contents are read exactly
as with `shallow=False`. A size difference ends the comparison without a read in either mode.

```python
import filecmp
import os
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    a = pathlib.Path(tmp, 'a.txt')
    b = pathlib.Path(tmp, 'b.txt')
    a.write_bytes(b'hello')
    b.write_bytes(b'HELLO')  # same size, different bytes
    os.utime(a, (1_000_000, 1_000_000))
    os.utime(b, (1_000_000, 1_000_000))

    # Same type, size and mtime: shallow trusts the signature and reads nothing
    assert filecmp.cmp(a, b) is True                  # O(1) - two os.stat calls
    assert filecmp.cmp(a, b, shallow=False) is False  # O(n) - reads both files

    # Different mtimes: shallow has to read the contents after all
    os.utime(b, (2_000_000, 2_000_000))
    assert filecmp.cmp(a, b) is False                 # O(n)

    # Different sizes are decided by the signature, whatever shallow says
    b.write_bytes(b'HELLO!')
    assert filecmp.cmp(a, b, shallow=False) is False  # O(1) - nothing read
```

### Deep Comparison and the Cache

A content comparison reads both files in fixed-size blocks and stops at the first block that
differs, so files that differ near the start are cheap and identical files cost their whole
length. The result is cached under both paths and both stat signatures; the next `cmp()` of the
same pair is a dictionary lookup until either signature changes. A rewrite that keeps both the
size and the mtime therefore returns the cached answer, which is what `clear_cache()` is for.

```python
import filecmp
import os
import pathlib
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    a = pathlib.Path(tmp, 'a.bin')
    b = pathlib.Path(tmp, 'b.bin')
    c = pathlib.Path(tmp, 'c.bin')
    a.write_bytes(b'\0' * 1_000_000)
    b.write_bytes(b'\1' + b'\0' * 999_999)
    c.write_bytes(b'\0' * 1_000_000)

    assert filecmp.cmp(a, b, shallow=False) is False  # O(1) - stops in the first block
    assert filecmp.cmp(a, c, shallow=False) is True   # O(n) - identical files are read to the end
    assert filecmp.cmp(a, c, shallow=False) is True   # O(1) - cached

    # Rewrite c with the same size and restore its mtime: the signature is unchanged
    before = c.stat()
    c.write_bytes(b'\2' * 1_000_000)
    os.utime(c, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert filecmp.cmp(a, c, shallow=False) is True   # O(1) - the stale cached answer

    filecmp.clear_cache()  # O(1)
    assert filecmp.cmp(a, c, shallow=False) is False  # O(1) - read again, differs at once
```

### Comparing Named Files

`cmpfiles()` is `cmp()` in a loop over names you supply, relative to two directories. It lists
nothing itself, and a name it cannot compare lands in the third list instead of raising.

```python
import filecmp
import os
import tempfile

with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
    for root, text in ((left, 'one'), (right, 'one')):
        with open(os.path.join(root, 'same.txt'), 'w') as f:
            f.write(text)
    for root, text in ((left, 'old'), (right, 'newer')):
        with open(os.path.join(root, 'changed.txt'), 'w') as f:
            f.write(text)

    match, mismatch, errors = filecmp.cmpfiles(
        left, right, ['same.txt', 'changed.txt', 'missing.txt']
    )  # O(f + s)
    assert match == ['same.txt']
    assert mismatch == ['changed.txt']
    assert errors == ['missing.txt']
```

## Comparing Directories

### Lazy Attributes

Building a `dircmp` records the two paths and nothing else, so it succeeds even for directories
that do not exist. Each attribute does its work the first time it is read: the name lists need
one `os.listdir` per side, the file and directory split needs two `os.stat` calls per common
name, and `same_files` and `diff_files` need one `cmp()` per common file. Read only what you use.

```python
import filecmp
import os
import tempfile

def write(path, text):
    with open(path, 'w') as f:
        f.write(text)

with tempfile.TemporaryDirectory() as tmp:
    left = os.path.join(tmp, 'left')
    right = os.path.join(tmp, 'right')
    for root in (left, right):
        os.makedirs(os.path.join(root, 'sub'))
        write(os.path.join(root, 'same.txt'), 'same')
    write(os.path.join(left, 'changed.txt'), 'old')
    write(os.path.join(right, 'changed.txt'), 'newer')
    write(os.path.join(left, 'only_left.txt'), 'x')

    comparison = filecmp.dircmp(left, right)          # O(1) - nothing read yet
    assert comparison.left_only == ['only_left.txt']  # O(e log e) - lists both sides
    assert comparison.right_only == []                # O(1) - computed with left_only
    assert comparison.common_dirs == ['sub']          # O(e) - two os.stat per common name
    assert comparison.same_files == ['same.txt']      # O(e + s) - one cmp() per common file
    assert comparison.diff_files == ['changed.txt']   # O(1) - computed with same_files

# Construction reads nothing, so a missing directory surfaces on first access
lazy = filecmp.dircmp('/no/such/left', '/no/such/right')  # O(1)
try:
    lazy.left_list
except FileNotFoundError:
    pass
else:
    raise AssertionError('a missing directory was listed')
```

### Recursing Into Subdirectories

`subdirs` builds one `dircmp` per common subdirectory without listing any of them, so a
recursive walk pays only for the levels and attributes it reads. `report()` covers one directory
pair; `report_partial_closure()` adds the immediate common subdirectories and
`report_full_closure()` the whole common tree. A directory that exists on one side only is
reported by name and never entered.

```python
import contextlib
import filecmp
import io
import os
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    left = os.path.join(tmp, 'left')
    right = os.path.join(tmp, 'right')
    for root in (left, right):
        os.makedirs(os.path.join(root, 'a', 'b'))
    os.makedirs(os.path.join(left, 'left_tree', 'deep'))
    with open(os.path.join(left, 'a', 'b', 'f.txt'), 'w') as f:
        f.write('left')
    with open(os.path.join(right, 'a', 'b', 'f.txt'), 'w') as f:
        f.write('right!')

    comparison = filecmp.dircmp(left, right)
    child = comparison.subdirs['a']  # O(e log e) - built, not yet listed
    assert type(child) is filecmp.dircmp
    assert child.right == os.path.join(right, 'a')

    one_level = io.StringIO()
    with contextlib.redirect_stdout(one_level):
        comparison.report()  # O(e log e + s) - this pair only
    assert 'f.txt' not in one_level.getvalue()
    assert "Only in {} : ['left_tree']".format(left) in one_level.getvalue()

    whole_tree = io.StringIO()
    with contextlib.redirect_stdout(whole_tree):
        comparison.report_full_closure()  # O(t log t + s) - every common pair
    assert "Differing files : ['f.txt']" in whole_tree.getvalue()
    assert 'diff {}'.format(os.path.join(left, 'left_tree')) not in whole_tree.getvalue()
```

### Comparing Contents in a Directory Tree

`dircmp` compares files the way `cmp()` does with its `shallow` setting. From Python 3.13 you can
pass `shallow=False`, which reads every common file whose size matches; before that, the same
result comes from `cmpfiles()` over `common_files`.

```python
import filecmp
import os
import sys
import tempfile

with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
    for root, text in ((left, 'hello'), (right, 'HELLO')):
        path = os.path.join(root, 'f.txt')
        with open(path, 'w') as f:
            f.write(text)
        os.utime(path, (1_000_000, 1_000_000))

    # Same size and mtime: the default shallow comparison calls them equal
    assert filecmp.dircmp(left, right).same_files == ['f.txt']  # O(e log e) - nothing read

    if sys.version_info >= (3, 13):
        deep = filecmp.dircmp(left, right, shallow=False)
        assert deep.diff_files == ['f.txt']  # O(e log e + s)
    else:
        common = filecmp.dircmp(left, right).common_files
        match, mismatch, errors = filecmp.cmpfiles(left, right, common, shallow=False)
        assert mismatch == ['f.txt']  # O(f + s)
```

## Common Patterns

### Listing Every Changed File

```python
import filecmp
import os
import tempfile

def changed_files(comparison):
    """Yield differing files across the common tree - O(t log t + s)."""
    for name in comparison.diff_files:
        yield os.path.join(comparison.left, name)
    for sub in comparison.subdirs.values():
        yield from changed_files(sub)

with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
    for root, text in ((left, 'v1'), (right, 'v22')):
        os.makedirs(os.path.join(root, 'pkg'))
        with open(os.path.join(root, 'pkg', 'mod.py'), 'w') as f:
            f.write(text)

    found = list(changed_files(filecmp.dircmp(left, right)))
    assert found == [os.path.join(left, 'pkg', 'mod.py')]
```

### Skipping Build Directories

`ignore` removes names before anything is stat'ed or compared, so excluding a large generated
directory saves its whole subtree. Passing `ignore` replaces `DEFAULT_IGNORES` rather than adding
to it.

```python
import filecmp
import os
import tempfile

with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
    for root in (left, right):
        os.makedirs(os.path.join(root, 'build'))
        os.makedirs(os.path.join(root, '.git'))

    assert '.git' in filecmp.DEFAULT_IGNORES
    assert filecmp.dircmp(left, right).common_dirs == ['build']

    ignoring = filecmp.dircmp(left, right, ignore=filecmp.DEFAULT_IGNORES + ['build'])
    assert ignoring.common_dirs == []  # O(e log e) - build is never stat'ed or entered
```

## Performance Best Practices

✅ **Do**:

- Preserve mtimes when copying (`shutil.copy2`), so shallow comparisons of the copy read nothing
- Read only the `dircmp` attributes you need; `left_only` and `right_only` cost a listing, not a
  stat or a read
- Add large generated directories to `ignore`, so their subtrees are never entered
- Call `clear_cache()` when a file may have been rewritten within the filesystem's mtime
  resolution

❌ **Avoid**:

- Assuming `shallow=True` never reads: equal sizes with different mtimes read both files
- Trusting a shallow match to prove equal contents: a same-size file with a matching mtime is
  never read
- `report_full_closure()` when only one level matters: it lists every common directory in the tree

## Version Notes

- **Python 3.13+**: `dircmp` accepts `shallow`; before that it always compares with
  `shallow=True`
- **All Python 3**: `shallow=True` still reads both files when their sizes match and their
  signatures do not

## Related Modules

- **[difflib](difflib.md)** - what differs between two files, where `filecmp` only says whether
- **[os](os.md)** - `os.stat` and `os.listdir`, the calls every comparison here is built from
- **[shutil](shutil.md)** - `copy2` preserves the mtime that shallow comparison relies on
- **[hashlib](hashlib.md)** - hash files once to compare many against each other
