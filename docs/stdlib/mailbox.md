# mailbox Module Complexity

The `mailbox` module presents five on-disk mail formats as one dictionary-like mapping from keys
to messages. Where a format keeps its messages decides every bound here: `mbox`, `MMDF` and
`Babyl` pack the whole mailbox into one file, so a key is a byte range and finding the ranges
means scanning the file; `Maildir` and `MH` give each message its own file, so a key is a
filename and finding the keys means listing a directory.

Nothing is read when a mailbox is constructed. The single-file formats build a table of contents
on the first operation that needs a key and keep it, so the scan is paid once per open; the
directory formats re-list on demand. Messages are read one at a time, and the module holds a
whole mailbox in memory only when you ask it to with `values()` or `items()`.

`n` is messages in the mailbox and `m` is bytes in one message. `F` is bytes in a single-file
mailbox and `B` is bytes in the messages a rewrite keeps, which is `F` less everything removed or
superseded. `e` is entries in the directory a directory
format lists - `cur` and `new` for `Maildir`, the folder itself for `MH` - and is at least `n`,
because both hold files that are not messages; `r` is entries in the mailbox's own directory,
where folders live. `H` is headers on a message's own header list, `T` is headers across it and its
subparts and `p` is its parts. `V` is headers in a `BabylMessage`'s visible set, `h` is bytes in a
message's headers, `f` is the characters in a flag or info string a call handles, and `L` is labels or
sequences on one message. `S` is bytes in `MH`'s `.mh_sequences` file, `K` is the named
sequences in the set being read or written, and `q` is the keys those sequences name once their
ranges are expanded - which a compact `1-100000` makes much the larger of the three. One filesystem call - open, stat, rename, unlink, link - is
treated as O(1), and a directory listing as O(e). A sequence name is treated as O(1) to carry,
compare and write, the way a folder's own names are: `K` counts them, and nothing here is
expressed in their bytes. A space cell marked *retained* is what the call still holds when it
returns; every line-oriented scan here - the single-file tables of contents and `.mh_sequences` -
peaks a line higher than that.

## Complexity Reference

### Mailbox

The abstract base. Its concrete methods are built from the subclass hooks, so their bounds are
the subclass's plus what the base adds.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.Mailbox(path, factory=None, create=True)` | O(1) | O(1) | Records the absolute path and the factory; subclasses do the format-specific setup |
| `Mailbox.add(message)` | O(1) | O(1) | Abstract: raises `NotImplementedError`. See each format |
| `Mailbox.remove(key)` | O(1) | O(1) | Abstract. `del mailbox[key]` calls it |
| `Mailbox.discard(key)` | Same as `remove()` | Same as `remove()` | `remove()` with `KeyError` swallowed |
| `Mailbox.get(key, default=None)` | Same as `mailbox[key]` | Same as `mailbox[key]` | `mailbox[key]` with `KeyError` swallowed |
| `Mailbox.get_message(key)` | O(1) | O(1) | Abstract. `mailbox[key]` calls it, or passes `get_file(key)` to `factory` when one was given |
| `Mailbox.get_bytes(key)` | O(1) | O(1) | Abstract |
| `Mailbox.get_file(key)` | O(1) | O(1) | Abstract |
| `Mailbox.get_string(key)` | O(m) | O(m) | Parses the bytes and renders them again, so the message is walked twice |
| `Mailbox.iterkeys()` | O(1) | O(1) | Abstract |
| `Mailbox.keys()` | O(`iterkeys` + n) | O(`iterkeys` + n) | Materializes the iterator |
| `Mailbox.itervalues()`, iterating a mailbox | O(`iterkeys` + n·`mailbox[key]`) | O(`iterkeys` + `mailbox[key]`) | One message at a time; a key the format can no longer resolve is skipped. With the default factory that is O(n·m) plus the key walk on every format but `MH`, where each message re-reads the sequences |
| `Mailbox.values()` | Same as iterating | O(`iterkeys` + n·`mailbox[key]`) | Holds every message at once |
| `Mailbox.iteritems()` | Same as iterating | Same as iterating | `itervalues()` paired with its key |
| `Mailbox.items()` | Same as iterating | O(`iterkeys` + n·`mailbox[key]`) | Holds every message at once |
| `Mailbox.pop(key, default=None)` | O(`mailbox[key]` + `remove`) | O(`mailbox[key]`) | Reads the message, then discards it |
| `Mailbox.popitem()` | O(`iterkeys` + `mailbox[key]` + `remove`) | O(`iterkeys` + `mailbox[key]`) | Takes the first key the format yields; raises `KeyError` when empty |
| `Mailbox.clear()` | O(`keys` + n·`remove`) | O(`keys`) | One `discard()` per key; on a single-file format the rewrite lands in the next `flush()` |
| `Mailbox.update(arg)` | O(u·`__setitem__`) | O(`__setitem__`) | u = pairs supplied; a missing key is collected and raises `KeyError` at the end, after the rest are written |
| `Mailbox.flush()`, `Mailbox.lock()`, `Mailbox.unlock()`, `Mailbox.close()` | O(1) | O(1) | Abstract |

### Maildir

One file per message, in `new` and `cur`. Changes are on disk when the call returns.

Every keyed operation resolves the key first. A name the mailbox already holds, whose file is
still there, is a dictionary hit and a stat; anything else re-lists both directories, O(e). The
rows below are the work after that lookup.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.Maildir(dirname, factory=None, create=True)` | O(1) | O(1) | Creates `tmp`, `new` and `cur` when absent; lists nothing. `create=False` on a missing directory raises `NoSuchMailboxError` |
| `Maildir.add(message)` | O(m) | O(m) | Writes `tmp`, then links into `new` or the message's own subdirectory; no directory scan |
| `Maildir.remove(key)`, `Maildir.discard(key)` | O(1) on a cached key, O(e) otherwise | O(e) | One unlink; a key the table of contents has lost costs a re-list |
| `Maildir.__setitem__(key, message)` | O(e + m) | O(e + m) | Adds under a temporary name, then renames over the old one; finding the temporary name costs a listing |
| `Maildir.get_message(key)` | O(m) | O(m) | Parses the file and restores the subdirectory, info and delivery date |
| `Maildir.get_bytes(key)` | O(m) | O(m) | |
| `Maildir.get_file(key)` | O(1) | O(1) | Opens the file and wraps it; nothing is read until you read it |
| `Maildir.iterkeys()` | O(e) | O(e) | Lists both directories, then stats each key |
| `Maildir.__contains__(key)`, `len(maildir)` | O(e) | O(e) | Both re-list; see *Counting Re-Lists the Directories* |
| `Maildir.get_info(key)` | O(f) | O(f) | Python 3.13+. Read out of the filename, not the message |
| `Maildir.set_info(key, info)` | O(f) | O(f) | Python 3.13+. One rename; identical info is not renamed |
| `Maildir.get_flags(key)` | O(f) | O(f) | Python 3.13+ |
| `Maildir.set_flags(key, flags)` | O(f log f) plus `set_info()` | O(f) | Python 3.13+. Distinct flag characters, sorted into the filename |
| `Maildir.add_flag(key, flag)`, `Maildir.remove_flag(key, flag)` | Same as `set_flags()` | O(f) | Python 3.13+. Read the current flags, then set the union or difference |
| `Maildir.colon` | O(1) | O(1) | Separator between a message's unique name and its info; set it to `'!'` where a filesystem forbids `':'` |
| `Maildir.list_folders()` | O(r) | O(r) | Lists the mailbox's own directory and stats each dotted entry |
| `Maildir.get_folder(folder)` | O(1) | O(1) | A `Maildir` on the subdirectory; a missing folder raises `NoSuchMailboxError` |
| `Maildir.add_folder(folder)` | O(1) | O(1) | Creates the subdirectory and its `maildirfolder` marker |
| `Maildir.remove_folder(folder)` | O(entries in the folder) | Same | Lists the folder to prove it empty, then walks it away; otherwise raises `NotEmptyError` |
| `Maildir.clean()` | O(t) | O(t) | t = entries in `tmp`; stats each and removes those untouched for 36 hours |
| `Maildir.flush()`, `Maildir.lock()`, `Maildir.unlock()`, `Maildir.close()` | O(1) | O(1) | No-ops: the format needs no locking and keeps nothing pending |
| `Maildir.next()` | O(e + m) on the first call, then O(m) | O(e + m) | A one-time iteration kept for backward compatibility; returns `None` at the end rather than stopping |

### mbox

Every message in one file, each introduced by a `From ` line.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.mbox(path, factory=None, create=True)` | O(1) | O(1) | Opens the file; the table of contents is not built yet. `create=False` on a missing file raises `NoSuchMailboxError` |
| First keyed operation on an open mailbox | O(F) | O(n) retained | Reads the file once to find the message boundaries, then keeps two offsets per message |
| `mbox.add(message)` | O(m) after the table of contents | O(m) | Appends; the file is not rewritten, so the pending work is a sync |
| `mbox.remove(key)` | O(1) after the table of contents | O(1) | Drops the offsets and marks the mailbox pending; the file is untouched until `flush()` |
| `mbox.__setitem__(key, message)` | O(m) after the table of contents | O(m) | Appends the replacement and points the key at it; the superseded copy goes at the next `flush()` |
| `mbox.get_message(key)` | O(m) after the table of contents | O(m) | Seeks to the offset and parses that range |
| `mbox.get_bytes(key, from_=False)` | O(m) after the table of contents | O(m) | `from_=True` keeps the `From ` line |
| `mbox.get_string(key, from_=False)` | O(m) after the table of contents | O(m) | `get_bytes()` parsed and rendered again, so the message is walked twice |
| `mbox.get_file(key, from_=False)` | O(1) after the table of contents | O(1) | A window on the mailbox file, not a copy; reading it is what costs, and it stops being readable when the mailbox closes |
| `mbox.iterkeys()` | O(n) after the table of contents | O(1) | Integer keys in insertion order, from the table of contents |
| `mbox.__contains__(key)`, `len(mbox)` | O(1) after the table of contents | O(1) | Dictionary operations on the offsets |
| `mbox.flush()` | O(B + n log n) after a removal or replacement, O(1) otherwise | O(n) held and O(B) on disk | Copies the surviving messages into a fresh file in key order and renames it over the old one, leaving removed and superseded bytes behind; after only `add()` calls it syncs and returns. A mailbox whose size changed underneath is rejected before anything is copied, with `ExternalClashError` |
| `mbox.lock()`, `mbox.unlock()` | O(1) | O(1) | An `lockf` range lock plus a `.lock` file beside the mailbox; a lock another process holds raises `ExternalClashError` |
| `mbox.close()` | Same as `flush()` | Same as `flush()` | Flushes, unlocks, then closes |

### MMDF

The same offsets and the same one-file costs as `mbox`, with each message wrapped in control-A
separators instead of a `From ` line.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.MMDF(path, factory=None, create=True)` | O(1) | O(1) | As `mbox` |
| `MMDF.get_bytes(key, from_=False)` | O(m) | O(m) | As `mbox` |
| `MMDF.get_file(key, from_=False)` | O(1) | O(1) | A window on the mailbox file, as `mbox` |

### MH

One file per message, named by its integer key, in a single directory.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.MH(path, factory=None, create=True)` | O(1) | O(1) | Creates the directory and an empty `.mh_sequences` when absent; lists nothing |
| `MH.add(message)` | O(e + n log n + m) | O(e + m) | The new key is one past the highest, so every add lists and sorts the folder first. An `MHMessage` adds a sequence rewrite, O(e + n log n + S + K·L + q log q) in time and O(e + q) retained in space |
| `MH.remove(key)` | O(1) | O(1) | Opens the numbered file to prove it exists, then unlinks it |
| `MH.__setitem__(key, message)` | O(m) | O(m) | Truncates the numbered file and writes. An `MHMessage` adds a sequence rewrite, O(e + n log n + S + K·L + q log q) in time and O(e + q) retained in space; each folder sequence is looked for in the message's list, which is the K·L |
| `MH.get_message(key)` | O(m + e + n log n + S + q log q + L²) | O(m + e + q) retained | Parses the file, then reads every sequence to label it; each label is checked against the ones already attached, so a message in many sequences pays for it |
| `MH.get_bytes(key)` | O(m) | O(m) | No sequence lookup, so it is the cheap way to read the text, and the one to use in a loop |
| `MH.get_file(key)` | O(1) | O(1) | Opens the file and wraps it; nothing is read until you read it |
| `MH.iterkeys()` | O(e + n log n) | O(e) | Lists the folder, keeps the numeric names and sorts them |
| `MH.__contains__(key)` | O(1) | O(1) | One stat on the numbered path |
| `len(mh)` | O(e + n log n) | O(e) | Counts what `iterkeys()` yields |
| `MH.get_sequences()` | O(e + n log n + S + q log q) | O(e + q) retained | Lists the folder to drop keys with no message, then parses the file; a `1-9` range expands to its members |
| `MH.set_sequences(sequences)` | O(K + q log q) | O(q) | `K` and `q` are the supplied mapping's names and keys. Rewrites the file, sorting each sequence and collapsing runs back into ranges; an empty sequence is visited and dropped, so K stands on its own |
| `MH.pack()` | O(e + n log n + S + q log q + c·q) | O(e + q) retained | Moves messages down to close numbering gaps; c = messages moved, each looked up in every sequence. A contiguous run at the front keeps its keys, and a mailbox with no gaps is left alone |
| `MH.list_folders()` | O(e) | O(e) | Stats each entry; the listing is built before the folders are picked out of it |
| `MH.get_folder(folder)` | O(1) | O(1) | An `MH` on the subdirectory; a missing folder raises `NoSuchMailboxError` |
| `MH.add_folder(folder)` | O(1) | O(1) | Creates the subdirectory and its `.mh_sequences` |
| `MH.remove_folder(folder)` | O(entries in the folder) | Same | Lists it and refuses anything but an empty folder with `NotEmptyError` |
| `MH.lock()`, `MH.unlock()` | O(1) | O(1) | Locks `.mh_sequences`, not the messages |
| `MH.flush()` | O(1) | O(1) | Nothing is pending: every change is written as it is made |
| `MH.close()` | O(1) | O(1) | Unlocks if locked |

### Babyl

One file, like `mbox`, plus a label list per message and a second copy of each message's headers.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.Babyl(path, factory=None, create=True)` | O(1) | O(1) | As `mbox` |
| First keyed operation on an open mailbox | O(F) | O(n + n·L) retained | The scan collects each message's labels along with its offsets |
| `Babyl.add(message)` | O(m + h) after the table of contents | O(m) | The headers are written twice, as received and again as the visible set. A `BabylMessage` is the exception, and not a usable one - see the warning below |
| `Babyl.get_message(key)` | O(m) | O(m) | Reassembles the original headers and body and attaches the labels. On a message stored from a `BabylMessage` it raises `AssertionError`, or silently loses the body up to its first blank line - see the warning below |
| `Babyl.get_bytes(key)` | O(m) | O(m) | Skips the visible headers |
| `Babyl.get_file(key)` | O(m) | O(m) | A copy in memory, unlike the window `mbox` and `MMDF` return |
| `Babyl.get_labels()` | O(n·L) after the table of contents | O(distinct labels) | Unions every message's labels, then drops the seven Babyl reserves |
| `Babyl.lock()`, `Babyl.unlock()` | O(1) | O(1) | As `mbox` |

### Message

`mailbox.Message` is an `email.message.Message` with a format's own state attached. The
subclasses differ only in that state, so they share these construction costs.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.Message(message=None)` | O(1) empty, O(T + p) from a message, O(m) otherwise | Same | An `email.message.Message` is deep-copied, so headers and subparts are independent of the original and payload bytes are not walked; bytes, a string or a file are parsed. A subclass carries its own state across too, at the cost of the accessors it goes through: O(f log f) for flags, O(L) for sequences or labels, O(V) for a visible set |

### MaildirMessage

Flags and delivery date live in the filename, so reading them never touches the headers.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.MaildirMessage(message=None)` | Same as `Message()` | Same | Defaults to subdirectory `new` with no flags and the current time |
| `MaildirMessage.get_info()`, `MaildirMessage.set_info(info)` | O(1) | O(1) | The info field itself, flags included; it is handed over, not copied |
| `MaildirMessage.get_flags()` | O(f) | O(f) | A slice of the info field; it never reaches the headers |
| `MaildirMessage.set_flags(flags)` | O(f log f) | O(f) | Sorted into the info field |
| `MaildirMessage.add_flag(flag)`, `MaildirMessage.remove_flag(flag)` | O(f log f) | O(f) | The union or difference, re-sorted |
| `MaildirMessage.get_subdir()`, `MaildirMessage.set_subdir(subdir)` | O(1) | O(1) | `'new'` or `'cur'`; anything else raises `ValueError` |
| `MaildirMessage.get_date()`, `MaildirMessage.set_date(date)` | O(1) | O(1) | Seconds since the epoch; a value that will not convert raises `TypeError` |

### mboxMessage

Flags live in the `Status` and `X-Status` headers, so every read and write scans the header list.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.mboxMessage(message=None)` | Same as `Message()` | Same | Takes its `From ` line from the source's unix-from when there is one |
| `mboxMessage.get_flags()` | O(H + f) | O(f) | Concatenates two header lookups, each a scan; nothing bounds what those headers hold |
| `mboxMessage.set_flags(flags)` | O(H + f log f) | O(f) | Splits the flags between the two headers and replaces both |
| `mboxMessage.add_flag(flag)` | O(H + f log f) | O(f) | Read then set |
| `mboxMessage.remove_flag(flag)` | O(H + f log f) | O(f), O(H + f) before 3.12 | Checks that one of the two headers is there before it reads and sets; that check listed every header name until 3.12 |
| `mboxMessage.get_from()`, `mboxMessage.set_from(from_, time_=None)` | O(1) | O(1) | `time_=True` appends the current UTC time |

### MHMessage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.MHMessage(message=None)` | Same as `Message()` | Same | Starts in no sequences |
| `MHMessage.get_sequences()` | O(L) | O(L) | A copy: changing the list does not reach the message |
| `MHMessage.set_sequences(sequences)` | O(L) | O(L) | Copied in |
| `MHMessage.add_sequence(sequence)` | O(L) | O(1) | Scans for a duplicate first; a non-string raises `TypeError` |
| `MHMessage.remove_sequence(sequence)` | O(L) | O(1) | A sequence that is not there is not an error |

### BabylMessage

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.BabylMessage(message=None)` | Same as `Message()` | Same | Starts with no labels and an empty visible set |
| `BabylMessage.get_labels()` | O(L) | O(L) | A copy, as `MHMessage.get_sequences()` is |
| `BabylMessage.set_labels(labels)` | O(L) | O(L) | Copied in |
| `BabylMessage.add_label(label)` | O(L) | O(1) | Scans for a duplicate first; a non-string raises `TypeError` |
| `BabylMessage.remove_label(label)` | O(L) | O(1) | A label that is not there is not an error |
| `BabylMessage.get_visible()` | O(V) | O(V) | A fresh copy each call, not a view: edit it and set it back |
| `BabylMessage.set_visible(visible)` | O(V) | O(V) | Copied in |
| `BabylMessage.update_visible()` | O(H + V·(H + V)) | O(V), O(H + V) before 3.12 | Refreshes each visible header from the message, drops those the message lost, and adds the six standard ones it has - which costs a header scan each even when the visible set is empty |

### MMDFMessage

Identical to `mboxMessage`: the format differs in its framing, not in where it keeps flags.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.MMDFMessage(message=None)` | Same as `Message()` | Same | |
| `MMDFMessage.get_flags()` | O(H + f) | O(f) | |
| `MMDFMessage.set_flags(flags)` | O(H + f log f) | O(f) | |
| `MMDFMessage.add_flag(flag)` | O(H + f log f) | O(f) | |
| `MMDFMessage.remove_flag(flag)` | O(H + f log f) | O(f), O(H + f) before 3.12 | |
| `MMDFMessage.get_from()`, `MMDFMessage.set_from(from_, time_=None)` | O(1) | O(1) | |

### Exceptions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `mailbox.Error` | O(1) | O(1) | Base of the four below |
| `mailbox.NoSuchMailboxError` | O(1) | O(1) | `create=False` and the mailbox is not there |
| `mailbox.NotEmptyError` | O(1) | O(1) | `remove_folder()` on a folder that still holds messages |
| `mailbox.ExternalClashError` | O(1) | O(1) | Another process holds the lock, took the filename, or changed the file's size between the scan and the flush |
| `mailbox.FormatError` | O(1) | O(1) | `MH` found a sequence specification it could not parse |

## Opening a Mailbox

### The Table of Contents Is Built on First Use

Constructing a single-file mailbox opens the file and stops. The first operation that needs a key
reads the whole file to find where each message starts and ends, and keeps two offsets per
message for as long as the mailbox is open. Re-opening pays the scan again.

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

def sample(subject):
    message = EmailMessage()
    message['Subject'] = subject
    message.set_content('body')
    return message

with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / 'archive.mbox')

    box = mailbox.mbox(path)       # O(1) - opens the file, reads nothing
    for index in range(4):
        box.add(sample(f's{index}'))  # O(m) each after the scan
    box.close()

    box = mailbox.mbox(path)       # O(1) again - nothing is read yet
    late = b'From sender\nSubject: late\n\nbody\n\n'
    with open(path, 'ab') as appended:
        appended.write(late)

    # The scan happens here, so it sees a message delivered after the open
    assert len(box) == 5           # O(F) once

    with open(path, 'ab') as appended:
        appended.write(late)
    assert len(box) == 5           # O(1): the offsets are kept, not re-read
    box.close()
```

### Directory Formats Have No Scan to Amortize

`Maildir` and `MH` find a message by name, so opening one costs nothing, and looking up a name
the mailbox already holds costs a stat. The price is that adding to `MH` lists the folder every
time, to work out the next integer key - which `Maildir` avoids by naming messages after the
clock and the process instead.

```python
import mailbox
import os
import tempfile
from email.message import EmailMessage
from pathlib import Path

def sample():
    message = EmailMessage()
    message['Subject'] = 's'
    message.set_content('body')
    return message

listed = []
real_listdir = os.listdir

def counting_listdir(path):
    listed.append(path)
    return real_listdir(path)

with tempfile.TemporaryDirectory() as directory:
    maildir = mailbox.Maildir(str(Path(directory) / 'md'))  # O(1)
    mh = mailbox.MH(str(Path(directory) / 'mh'))            # O(1)
    for _ in range(5):
        maildir.add(sample())
        mh.add(sample())

    os.listdir = counting_listdir
    try:
        listed.clear()
        maildir.add(sample())   # O(m) - no listing
        maildir_listings = len(listed)

        listed.clear()
        mh.add(sample())        # O(e + n log n + m) - lists to find the next key
        mh_listings = len(listed)
    finally:
        os.listdir = real_listdir

    assert maildir_listings == 0
    assert mh_listings == 1
    assert sorted(mh.keys()) == [1, 2, 3, 4, 5, 6]
```

## Reading Messages

### A Parsed Message, Bytes, or a Window

`get_message()` parses; `get_bytes()` hands back the stored bytes; `get_file()` returns something
to read from. On `mbox` and `MMDF` that last one is a window onto the open mailbox file, so
building it is O(1) whatever the message weighs, and reading it is where the bytes are paid for.
`Babyl` cannot do that - its stored form interleaves two header copies - so its `get_file()`
reassembles the message in memory first.

```python
import mailbox
import tempfile
import tracemalloc
from email.message import EmailMessage
from pathlib import Path

def sample(size):
    message = EmailMessage()
    message['Subject'] = 's'
    message.set_content('x' * size)
    return message

def peak(make):
    tracemalloc.start()
    try:
        make()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

with tempfile.TemporaryDirectory() as directory:
    box = mailbox.mbox(str(Path(directory) / 'archive.mbox'))
    box.add(sample(200_000))
    box.close()

    box = mailbox.mbox(str(Path(directory) / 'archive.mbox'))
    assert len(box) == 1                              # O(F) scan

    view = box.get_file(0)                            # O(1) - a window
    assert peak(lambda: box.get_file(0)) < 10_000     # no message-sized copy
    assert len(view.read()) > 200_000                 # O(m) - here are the bytes

    assert peak(lambda: box.get_bytes(0)) > 200_000   # O(m)
    box.close()

    babyl = mailbox.Babyl(str(Path(directory) / 'archive.babyl'))
    babyl.add(sample(200_000))
    babyl.close()

    babyl = mailbox.Babyl(str(Path(directory) / 'archive.babyl'))
    assert len(babyl) == 1
    assert peak(lambda: babyl.get_file(0)) > 200_000  # O(m) - a copy, not a window
    babyl.close()
```

### Iterating Holds One Message; values() Holds Them All

Iterating a mailbox yields one message at a time and keeps only that one, so what you retain is
whatever you build from it. `values()` and `items()` are the same walk with a list around it, so
they cost the whole mailbox in memory.

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

def sample(subject):
    message = EmailMessage()
    message['Subject'] = subject
    message.set_content('body')
    return message

with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / 'archive.mbox')
    box = mailbox.mbox(path)
    for index in range(3):
        box.add(sample(f's{index}'))
    box.close()

    box = mailbox.mbox(path)
    subjects = [message['Subject'] for message in box]  # O(m) at a time
    assert subjects == ['s0', 's1', 's2']

    everything = box.values()          # O(n·m) held at once
    assert len(everything) == 3

    keys = [key for key, _ in box.iteritems()]  # O(m) at a time, keeping only the keys
    assert keys == [0, 1, 2]
    box.close()
```

## Adding and Removing Messages

### Removal Costs a Rewrite, Addition Does Not

A single-file mailbox appends a new message to the end of the file, so `add()` writes the message
and nothing else. It cannot punch a hole, so `remove()` just drops the offsets and
`__setitem__()` appends the replacement and repoints the key; either way the old bytes stay put
until the next `flush()`, which copies the survivors into a fresh file and renames it over the
old one. Batch removals behind one `flush()` rather than paying the rewrite per message.

```python
import mailbox
import os
import tempfile
from email.message import EmailMessage
from pathlib import Path

def sample(subject):
    message = EmailMessage()
    message['Subject'] = subject
    message.set_content('body')
    return message

with tempfile.TemporaryDirectory() as directory:
    path = str(Path(directory) / 'archive.mbox')
    box = mailbox.mbox(path)
    for index in range(10):
        box.add(sample(f's{index}'))
    box.close()

    box = mailbox.mbox(path)
    assert len(box) == 10

    inode = os.stat(path).st_ino
    inode_size = os.path.getsize(path)
    box.add(sample('new'))   # O(m) - appended
    box.flush()              # O(1) - a sync, the file is not replaced
    assert os.stat(path).st_ino == inode

    box.remove(0)            # O(1) - the offsets are dropped, the bytes stay
    box.remove(1)            # O(1) - the offsets are dropped, the bytes stay
    box.flush()              # O(B + n log n) - the survivors are copied to a new file
    assert os.stat(path).st_ino != inode
    assert os.path.getsize(path) < inode_size

    assert sorted(box.keys()) == [2, 3, 4, 5, 6, 7, 8, 9, 10]
    box.close()
```

### A Mailbox Changed Underneath You

`flush()` compares the file's size with what the scan recorded. A mismatch means another process
wrote while the offsets were being held, and rewriting from stale offsets would lose mail, so it
raises `ExternalClashError` instead - before it has copied anything.

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

def sample(subject):
    message = EmailMessage()
    message['Subject'] = subject
    message.set_content('body')
    return message

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'archive.mbox'
    box = mailbox.mbox(str(path))
    box.add(sample('first'))
    box.add(sample('second'))
    box.close()

    box = mailbox.mbox(str(path))
    box.remove(0)  # O(F) here: the scan, then O(1) to drop the offsets

    with open(path, 'ab') as appended:  # another process delivers mail
        appended.write(b'From someone\nSubject: third\n\nbody\n\n')

    try:
        box.flush()  # O(1) - the size check comes before any copying
    except mailbox.ExternalClashError as error:
        assert 'changed' in str(error)
    else:
        raise AssertionError('a resized mailbox was rewritten')
```

## Counting and Iterating

### Counting Re-Lists the Directories

`Maildir` keeps no message count. `len()`, `in` and `iterkeys()` each go back to `cur` and `new`,
so counting in a loop is a directory listing per turn. The one shortcut is a mailbox that has
been quiet: more than about two seconds after the last listing, an unchanged modification time on
both directories lets the call reuse what it has. Take the count once and hold it.

```python
import mailbox
import os
import tempfile
from email.message import EmailMessage
from pathlib import Path

listed = []
real_listdir = os.listdir

def counting_listdir(path):
    listed.append(path)
    return real_listdir(path)

with tempfile.TemporaryDirectory() as directory:
    maildir = mailbox.Maildir(str(Path(directory) / 'md'))
    for index in range(5):
        message = EmailMessage()
        message['Subject'] = f's{index}'
        message.set_content('body')
        maildir.add(message)

    os.listdir = counting_listdir
    try:
        listed.clear()
        assert len(maildir) == 5   # O(e) - lists cur and new
        first = len(listed)

        listed.clear()
        assert len(maildir) == 5   # O(e) again - the count is not cached
        second = len(listed)
    finally:
        os.listdir = real_listdir

    assert first == 2 and second == 2
```

Looking a message up is the opposite: a key the mailbox has already seen is a dictionary hit plus
one stat, and only a key it has lost goes back to the directories.

```python
import mailbox
import os
import tempfile
from email.message import EmailMessage
from pathlib import Path

listed = []
real_listdir = os.listdir

def counting_listdir(path):
    listed.append(path)
    return real_listdir(path)

with tempfile.TemporaryDirectory() as directory:
    maildir = mailbox.Maildir(str(Path(directory) / 'md'))
    message = EmailMessage()
    message['Subject'] = 's'
    message.set_content('body')
    key = maildir.add(message)
    assert key in maildir

    os.listdir = counting_listdir
    try:
        listed.clear()
        assert maildir[key]['Subject'] == 's'  # O(m) - no listing
        cached = len(listed)

        listed.clear()
        assert maildir.get('absent') is None   # O(e) - the miss goes back to the directories
        missing = len(listed)
    finally:
        os.listdir = real_listdir

    assert cached == 0
    assert missing == 2
```

## Flags, Sequences and Labels

### Where a Format Keeps Its Flags

`Maildir` writes flags into the filename, so reading them is a string slice that never looks at
the message. `mbox` and `MMDF` write them into the `Status` and `X-Status` headers, so every read
scans the header list and every write replaces two headers. On a message with many headers that
difference is the whole cost of the call.

```python
import mailbox

maildir_message = mailbox.MaildirMessage()
maildir_message.set_flags('SR')          # O(f log f) - sorted into the info field
assert maildir_message.get_flags() == 'RS'   # O(f)
assert maildir_message.get_info() == '2,RS'
assert maildir_message.items() == []     # no header was touched

mbox_message = mailbox.mboxMessage()
for index in range(50):
    mbox_message[f'X-Trace-{index}'] = 'v'
mbox_message.set_flags('RO')             # O(H + f log f) - two headers replaced
assert mbox_message.get_flags() == 'RO'  # O(H) - two header scans
assert mbox_message['Status'] == 'RO'

mbox_message.add_flag('D')               # O(H + f log f)
assert set(mbox_message.get_flags()) == {'R', 'O', 'D'}
assert mbox_message['X-Status'] == 'D'
```

`Maildir` can also set the flags of a stored message without reading it, by renaming the file.

```python
import mailbox
import sys
import tempfile
from email.message import EmailMessage
from pathlib import Path

if sys.version_info >= (3, 13):
    with tempfile.TemporaryDirectory() as directory:
        maildir = mailbox.Maildir(str(Path(directory) / 'md'))
        message = EmailMessage()
        message['Subject'] = 's'
        message.set_content('body')
        key = maildir.add(message)

        maildir.set_flags(key, 'SR')          # O(f log f) plus one rename
        assert maildir.get_flags(key) == 'RS'  # O(f) - read out of the filename
        assert maildir.get_info(key) == '2,RS'

        maildir.add_flag(key, 'F')
        assert set(maildir.get_flags(key)) == {'R', 'S', 'F'}
        maildir.remove_flag(key, 'R')
        assert set(maildir.get_flags(key)) == {'S', 'F'}
```

### A BabylMessage Cannot Be Read Back

!!! warning "Store a plain message in a `Babyl` mailbox"
    `add()` writes each message's headers twice, the second copy being the visible set. Handed a
    `BabylMessage`, it writes that second copy empty - a visible set you gave it is dropped too -
    and what lands on disk is malformed. Reading it back searches for the blank line that should
    have closed the visible headers, and what that search runs into decides the damage. A body
    with no blank line in it has none to find, so `get_message()`, `get_bytes()` and `get_file()`
    all raise `AssertionError`. A body that does have one reads back **successfully, with
    everything before that blank line gone**. The silent case is the dangerous one. Both hold on
    every Python 3 version this page covers, so hand `Babyl.add()` an `email.message.Message`.

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    plain = EmailMessage()
    plain['Subject'] = 'hello'
    plain.set_content('one paragraph only\n')

    readable = mailbox.Babyl(str(Path(directory) / 'ok.babyl'))
    readable.add(plain)                      # O(m + h) - the headers go in twice
    readable.close()

    readable = mailbox.Babyl(str(Path(directory) / 'ok.babyl'))
    assert readable.get_message(0)['Subject'] == 'hello'   # O(m)
    readable.close()

    broken = mailbox.Babyl(str(Path(directory) / 'broken.babyl'))
    broken.add(mailbox.BabylMessage(plain))  # the visible copy is written empty
    broken.close()

    broken = mailbox.Babyl(str(Path(directory) / 'broken.babyl'))
    try:
        broken.get_message(0)                # O(m), and it does not get that far
    except AssertionError:
        pass
    else:
        raise AssertionError('a BabylMessage round-tripped')
    broken.close()

    # A blank line in the body is worse: the read succeeds and loses the start
    two_paragraphs = EmailMessage()
    two_paragraphs['Subject'] = 'hello'
    two_paragraphs.set_content('first paragraph\n\nsecond paragraph\n')

    silent = mailbox.Babyl(str(Path(directory) / 'silent.babyl'))
    silent.add(mailbox.BabylMessage(two_paragraphs))
    silent.close()

    silent = mailbox.Babyl(str(Path(directory) / 'silent.babyl'))
    assert silent.get_message(0).get_payload() == 'second paragraph\n'  # O(m)
    silent.close()
```

### Sequences and Labels Come Back as Copies

`MHMessage.get_sequences()`, `BabylMessage.get_labels()` and `BabylMessage.get_visible()` each
build a new object. Editing what they return changes nothing; set it back to make it stick.

```python
import mailbox

message = mailbox.MHMessage()
message.set_sequences(['unseen', 'flagged'])   # O(L)

sequences = message.get_sequences()            # O(L) - a copy
sequences.append('replied')
assert message.get_sequences() == ['unseen', 'flagged']

message.set_sequences(sequences)               # O(L) - now it sticks
assert message.get_sequences() == ['unseen', 'flagged', 'replied']

message.add_sequence('unseen')                 # O(L) - scans for the duplicate
assert message.get_sequences().count('unseen') == 1
message.remove_sequence('absent')              # not an error
```

```python
import mailbox

message = mailbox.BabylMessage()
message['Subject'] = 'hello'
message['From'] = 'someone@example.com'
message.add_label('answered')                  # O(L)

assert message.get_labels() == ['answered']    # O(L) - a copy
assert message.get_visible() is not message.get_visible()

message.update_visible()                       # O(H + V·(H + V))
assert message.get_visible()['Subject'] == 'hello'

message['Subject'] = 'hello'
del message['Subject']
message.update_visible()
assert 'Subject' not in message.get_visible()
```

### MH Sequences Cost a Folder Listing

Iterating an `MH` mailbox pays that per message: n listings of a folder that holds n messages,
which is quadratic before the sequence file is counted. Reach for `get_bytes()` in a loop, and
`get_sequences()` once outside it.

`MH` stores sequences in one `.mh_sequences` file, as ranges. Reading them expands the ranges -
so the cost follows the keys named, not the bytes stored - and lists the folder first, to drop
keys whose message is gone. That listing is why `get_message()` costs one and `get_bytes()` does
not.

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    mh = mailbox.MH(str(Path(directory) / 'mh'))
    for index in range(5):
        message = EmailMessage()
        message['Subject'] = f's{index}'
        message.set_content('body')
        mh.add(message)                        # O(e + n log n + m) each

    mh.set_sequences({'unseen': [1, 2, 3, 5]})  # O(K + q log q) - runs become ranges
    assert '1-3 5' in (Path(directory) / 'mh' / '.mh_sequences').read_text()

    assert mh.get_sequences() == {'unseen': [1, 2, 3, 5]}  # O(e + n log n + S + q log q)

    mh.remove(2)                                # O(1)
    assert mh.get_sequences() == {'unseen': [1, 3, 5]}  # the gone key is dropped

    labelled = mh.get_message(1)                # O(m + e + n log n + S + q log q + L²)
    assert labelled.get_sequences() == ['unseen']

    mh.pack()                                   # O(e + n log n + S + q log q + c·q)
    assert sorted(mh.keys()) == [1, 2, 3, 4]
```

## Converting Between Formats

Handing a message of one format's class to another's constructor copies the message and
translates what it can: Maildir flags become mbox `Status` letters, MH sequences become Babyl
labels. The copy is the deep copy every `Message` constructor makes, and the translation is a
fixed number of flag updates on top of it.

```python
import mailbox

source = mailbox.MaildirMessage()
source['Subject'] = 'hello'
source.set_payload('body')
source.set_flags('RS')          # replied, seen
source.set_subdir('cur')

converted = mailbox.mboxMessage(source)   # O(T + p) plus the translation
assert converted['Subject'] == 'hello'
assert set(converted.get_flags()) == {'R', 'O', 'A'}

# The copy is independent of the original
converted['X-Added'] = 'yes'
assert 'X-Added' not in source

as_mh = mailbox.MHMessage(source)
assert 'replied' in as_mh.get_sequences()
```

## Common Patterns

### Filtering One Mailbox Into Another

Read lazily and write as you go: what grows with the archive is the two offset tables, not the
messages. Doing it into a second mailbox avoids the rewrite that removing in place would cost.

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    source_path = str(Path(directory) / 'all.mbox')
    kept_path = str(Path(directory) / 'kept.mbox')

    source = mailbox.mbox(source_path)
    for index in range(6):
        message = EmailMessage()
        message['Subject'] = 'keep' if index % 2 else 'drop'
        message.set_content(f'body {index}')
        source.add(message)
    source.close()

    source = mailbox.mbox(source_path)
    kept = mailbox.mbox(kept_path)
    try:
        for message in source:                # O(m) at a time
            if message['Subject'] == 'keep':
                kept.add(message)             # O(m)
    finally:
        kept.close()                          # O(1) - only additions pending
        source.close()

    kept = mailbox.mbox(kept_path)
    assert len(kept) == 3
    assert {message['Subject'] for message in kept} == {'keep'}
    kept.close()
```

### Refusing to Create, and Refusing to Delete

```python
import mailbox
import tempfile
from email.message import EmailMessage
from pathlib import Path

with tempfile.TemporaryDirectory() as directory:
    try:
        mailbox.mbox(str(Path(directory) / 'absent.mbox'), create=False)
    except mailbox.NoSuchMailboxError as error:
        assert isinstance(error, mailbox.Error)
    else:
        raise AssertionError('a missing mailbox was opened')

    maildir = mailbox.Maildir(str(Path(directory) / 'md'))
    folder = maildir.add_folder('work')        # O(1)
    assert maildir.list_folders() == ['work']  # O(r)

    message = EmailMessage()
    message['Subject'] = 's'
    message.set_content('body')
    folder.add(message)

    try:
        maildir.remove_folder('work')          # O(entries in the folder) - lists it first
    except mailbox.NotEmptyError as error:
        assert 'work' in str(error)
    else:
        raise AssertionError('a folder holding mail was removed')
```

## Performance Best Practices

✅ **Do**:

- Keep one mailbox object open for a run of operations: the single-file scan is paid per open
- Batch removals from `mbox`, `MMDF` or `Babyl` behind one `flush()`, since each flush that has a
  removal pending copies every surviving message into a new file
- Take `len()` of a `Maildir` once; it is not cached, and a mailbox that has just changed is
  listed again on every call
- Use `get_bytes()` when you want the text and `get_file()` when you want to stream it - only
  `get_message()` has to parse, and only `MH.get_message()` also lists the folder
- Prefer `Maildir` over `MH` for a mailbox that grows: `MH` lists and sorts the folder on every
  add
- Iterate a mailbox instead of calling `values()` or `items()` on it

❌ **Avoid**:

- `values()` or `items()` on a large mailbox - that is the one thing here that holds every
  message at once
- Removing from a single-file mailbox inside a loop that flushes - every survivor is copied
  again per message
- Reading a message just to check a Maildir flag; the filename already has it
- Handing `Babyl.add()` a `BabylMessage` - what it stores comes back raising, or short
- Iterating an `MH` mailbox for the message bodies - every `get_message()` re-reads the
  sequences; walk the keys and call `get_bytes()`
- Calling `MH.pack()` while you hold keys - a moved message answers to a new one

## Version Notes

- **Python 3.13+**: `Maildir` can read and write a stored message's flags by key -
  `get_info()`, `set_info()`, `get_flags()`, `set_flags()`, `add_flag()` and `remove_flag()` -
  which renames the file instead of reading the message. On earlier versions the same flags are
  reachable only through a `MaildirMessage`
- **Python 3.12+**: asking a message whether it has a header stopped building a list of every
  header name it has, which is the peak memory of `mboxMessage.remove_flag()`,
  `MMDFMessage.remove_flag()` and `BabylMessage.update_visible()` - the three calls here that
  ask. Their time is unchanged
- **Python 3.13+**: `Maildir` ignores dotted entries in `cur` and `new`, so an editor's temporary
  file is no longer counted as a message
- **All Python 3**: a `Mailbox` is not safe against another process writing the same mailbox
  unless you `lock()` it; `Maildir`'s `lock()` is a no-op because the format does not need one

## Related Modules

- **[email](email.md)** - the message objects every class here subclasses, and the parser that
  reads them
- **[os](os.md)** - the directory listings and renames the directory formats are built on
- **[smtplib](smtplib.md)** - sending what a mailbox stores
