# codecs Module Complexity

The `codecs` module is the registry behind every `str.encode()` and `bytes.decode()`: it maps an
encoding name to a codec, and it provides the incremental and stream classes that encode or decode
text a piece at a time. Encoding and decoding are linear in the input for the standard text
codecs, with the two exceptions named below.

`n` is the length of the input to one call - characters for a `str`, bytes for a bytes-like
object - and the output of a text codec is O(n) as well. `c` is the length of one chunk handed to
an incremental or stream call, `t` the undecoded tail an incremental decoder keeps between calls,
`L` the characters in one line, `b` the characters a `StreamReader` already holds from an earlier
`read()`, `r` the registered search functions, `m` the entries in a mapping or table, and `f` the
length of the slice an encoding or decoding error covers (`exc.end - exc.start`). Linear bounds on
encoding and decoding, whole or incremental, are for the standard text codecs other than
`punycode`, which is priced in its own section. Encoding names are short, so normalizing one is
priced at O(1). A search function or error
handler you supply adds its own cost to every call that reaches it.

## Complexity Reference

### Encoding and decoding

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.encode(obj, encoding='utf-8', errors='strict')` | O(n) | O(n) | For the standard text codecs; `punycode` is O(n·u), u = distinct non-ASCII characters |
| `codecs.decode(obj, encoding='utf-8', errors='strict')` | O(n) | O(n) | Accepts any bytes-like object; `punycode` is O(n²), and a decompressing codec such as `zlib_codec` returns its decompressed size |
| `codecs.iterencode(iterator, encoding, errors='strict', **kwargs)` | O(n) total | O(c) | Lazy: takes a chunk only when it needs more output, and encodes it with an incremental encoder |
| `codecs.iterdecode(iterator, encoding, errors='strict', **kwargs)` | O(n) total | O(t + c) | Lazy: takes a chunk only when it needs more output; O(n²) for UTF-7 with long non-ASCII runs, see `IncrementalDecoder` |

### Codec registry

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.lookup(encoding)` | O(1) | O(1) | Cached by normalized name (case, spaces and hyphens folded). The first lookup of a name calls the search functions in order, O(r); a name none recognizes is never cached |
| `codecs.register(search_function)` | O(1) | O(1) | Appends to the search list |
| `codecs.unregister(search_function)` | O(r + k) | O(1) | k = cached names. Removing a registered function also empties the lookup cache, so every name is searched afresh once |
| `codecs.getencoder(encoding)`, `codecs.getdecoder(encoding)` | O(1) | O(1) | `lookup(encoding).encode` and `.decode` |
| `codecs.getincrementalencoder(encoding)`, `codecs.getincrementaldecoder(encoding)` | O(1) | O(1) | Raises `LookupError` if the codec has none |
| `codecs.getreader(encoding)`, `codecs.getwriter(encoding)` | O(1) | O(1) | `lookup(encoding).streamreader` and `.streamwriter` |

### CodecInfo

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.CodecInfo(encode, decode, streamreader=None, streamwriter=None, incrementalencoder=None, incrementaldecoder=None, name=None)` | O(1) | O(1) | What a search function returns; unpacks as the 4-tuple `(encode, decode, streamreader, streamwriter)` |
| `CodecInfo.name`, `CodecInfo.encode`, `CodecInfo.decode`, `CodecInfo.incrementalencoder`, `CodecInfo.incrementaldecoder`, `CodecInfo.streamreader`, `CodecInfo.streamwriter` | O(1) | O(1) | Attribute reads |

### Codec

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Codec.encode(input, errors='strict')`, `Codec.decode(input, errors='strict')` | O(n) | O(n) | Stateless; return `(output, length consumed)`. The base class raises `NotImplementedError`; `StreamWriter` and `StreamReader` subclass it |

### IncrementalEncoder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.IncrementalEncoder(errors='strict')` | O(1) | O(1) | |
| `IncrementalEncoder.encode(object, final=False)` | O(c) | O(c) | O(n) in total however the input is split, for the codecs `codecs.encode()` prices at O(n) |
| `IncrementalEncoder.reset()`, `IncrementalEncoder.getstate()`, `IncrementalEncoder.setstate(state)` | O(1) | O(1) | |

### IncrementalDecoder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.IncrementalDecoder(errors='strict')` | O(1) | O(1) | |
| `IncrementalDecoder.decode(object, final=False)` | O(t + c) | O(t + c) | t = undecoded tail kept from the last call: under 4 bytes for UTF-8, UTF-16 and UTF-32, but the whole current shifted run for UTF-7 |
| `IncrementalDecoder.reset()`, `IncrementalDecoder.getstate()`, `IncrementalDecoder.setstate(state)` | O(1) | O(1) | |

### BufferedIncrementalEncoder and BufferedIncrementalDecoder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.BufferedIncrementalEncoder(errors='strict')`, `codecs.BufferedIncrementalDecoder(errors='strict')` | O(1) | O(1) | Undocumented base classes; the standard UTF decoders are built on the decoder |
| `BufferedIncrementalEncoder.encode(input, final=False)`, `BufferedIncrementalDecoder.decode(input, final=False)` | O(t + c) | O(t + c) | Joins the kept tail to the new input before converting |
| `BufferedIncrementalEncoder.reset()`, `BufferedIncrementalEncoder.getstate()`, `BufferedIncrementalEncoder.setstate(state)`, `BufferedIncrementalDecoder.reset()`, `BufferedIncrementalDecoder.getstate()`, `BufferedIncrementalDecoder.setstate(state)` | O(1) | O(1) | |

### StreamWriter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.StreamWriter(stream, errors='strict')` | O(1) | O(1) | |
| `StreamWriter.write(object)` | O(n) | O(n) | Encodes the whole argument, then makes one `stream.write()` |
| `StreamWriter.writelines(list)` | O(n) | O(n) | n = total characters; joins the list into one string first |
| `StreamWriter.reset()`, `StreamWriter.seek(offset, whence=0)` | O(1) | O(1) | |

### StreamReader

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.StreamReader(stream, errors='strict')` | O(1) | O(1) | Reads nothing |
| `StreamReader.read(size=-1, chars=-1, firstline=False)` | O(n + b) | O(n + b) | n = bytes taken from the stream. It takes `size` bytes at a time until it holds `chars` characters (`size` characters when `chars` is omitted), or all the rest when `size` is omitted - even if `chars` is small. O(n²) when `chars` is many times `size`, since each step re-copies the characters gathered so far, and O(n²) for UTF-7, as for its incremental decoder |
| `StreamReader.readline(size=None, keepends=True)` | O(L·(L + b)) | O(L + b) | Every refill re-splits the line read so far and copies what is still buffered; `io.TextIOWrapper.readline()` is O(L) |
| Iterating a `StreamReader` | O(L·(L + b)) per line | O(L + b) | One `readline()` per line |
| `StreamReader.readlines(sizehint=None, keepends=True)` | O(n) | O(n) | Reads the whole stream; `sizehint` is ignored |
| `StreamReader.reset()`, `StreamReader.seek(offset, whence=0)` | O(1) | O(1) | Drop the buffered bytes and characters |

### StreamReaderWriter

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.open(filename, mode='r', encoding=None, errors='strict', buffering=-1)` | O(1) | O(1) | With an encoding, a `StreamReaderWriter` over the file opened in binary mode; deprecated in 3.14 in favour of `open()` |
| `codecs.StreamReaderWriter(stream, Reader, Writer, errors='strict')` | O(1) | O(1) | Builds one reader and one writer over the stream |
| `StreamReaderWriter.read(size=-1)`, `StreamReaderWriter.readlines(sizehint=None)` | O(n) | O(n) | Forwarded to the `StreamReader` |
| `StreamReaderWriter.readline(size=None)` | O(L·(L + b)) | O(L + b) | Forwarded to the `StreamReader` |
| `StreamReaderWriter.write(data)`, `StreamReaderWriter.writelines(list)` | O(n) | O(n) | Forwarded to the `StreamWriter` |
| `StreamReaderWriter.reset()`, `StreamReaderWriter.seek(offset, whence=0)` | O(1) | O(1) | |
| `StreamReaderWriter.encoding` | O(1) | O(1) | The name `codecs.open()` was given |

### StreamRecoder

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.EncodedFile(file, data_encoding, file_encoding=None, errors='strict')` | O(1) | O(1) | Returns a `StreamRecoder` |
| `codecs.StreamRecoder(stream, encode, decode, Reader, Writer, errors='strict')` | O(1) | O(1) | |
| `StreamRecoder.read(size=-1)`, `StreamRecoder.readlines(sizehint=None)` | O(n) | O(n) | Decodes with the file encoding, then encodes with the data encoding |
| `StreamRecoder.readline(size=None)` | O(L·(L + b)) | O(L + b) | The reader's `readline()`, then one encode |
| `StreamRecoder.write(data)`, `StreamRecoder.writelines(list)` | O(n) | O(n) | Decodes with the data encoding, then encodes with the file encoding |
| `StreamRecoder.reset()`, `StreamRecoder.seek(offset, whence=0)` | O(1) | O(1) | |
| `StreamRecoder.data_encoding`, `StreamRecoder.file_encoding` | O(1) | O(1) | The names `EncodedFile()` was given |

### Error handlers

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.register_error(name, error_handler)` | O(1) | O(1) | One dict entry. A codec calls the handler once per error it reports; how much one error covers depends on the codec |
| `codecs.lookup_error(name)` | O(1) | O(1) | Dict lookup; raises `LookupError` for an unknown name |
| `codecs.strict_errors(exception)` | O(1) | O(1) | Raises the exception it is given |
| `codecs.ignore_errors(exception)` | O(1) | O(1) | Returns an empty replacement |
| `codecs.replace_errors(exception)` | O(f) | O(f) | One `?` per character when encoding; one U+FFFD for the whole slice when decoding |
| `codecs.backslashreplace_errors(exception)` | O(f) | O(f) | |
| `codecs.xmlcharrefreplace_errors(exception)`, `codecs.namereplace_errors(exception)` | O(f) | O(f) | Encoding errors only |

### Character maps

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.charmap_build(decoding_table)` | O(m) | O(m) | m = table length; the encoding table a charmap codec uses |
| `codecs.charmap_encode(str, errors=None, mapping=None)`, `codecs.charmap_decode(data, errors=None, mapping=None)` | O(n) | O(n) | |
| `codecs.make_identity_dict(rng)` | O(m) | O(m) | |
| `codecs.make_encoding_map(decoding_map)` | O(m) | O(m) | A character that several bytes decode to maps to `None`, so encoding it fails |

### Codec helper functions

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.ascii_encode`, `codecs.ascii_decode`, `codecs.latin_1_encode`, `codecs.latin_1_decode`, `codecs.utf_7_encode`, `codecs.utf_7_decode`, `codecs.utf_8_encode`, `codecs.utf_8_decode` | O(n) | O(n) | Undocumented C functions; each returns `(output, length consumed)` |
| `codecs.utf_16_encode`, `codecs.utf_16_decode`, `codecs.utf_16_le_encode`, `codecs.utf_16_le_decode`, `codecs.utf_16_be_encode`, `codecs.utf_16_be_decode`, `codecs.utf_32_encode`, `codecs.utf_32_decode`, `codecs.utf_32_le_encode`, `codecs.utf_32_le_decode`, `codecs.utf_32_be_encode`, `codecs.utf_32_be_decode` | O(n) | O(n) | As above |
| `codecs.utf_16_ex_decode`, `codecs.utf_32_ex_decode` | O(n) | O(n) | Also return the byte order a BOM announced |
| `codecs.unicode_escape_encode`, `codecs.unicode_escape_decode`, `codecs.raw_unicode_escape_encode`, `codecs.raw_unicode_escape_decode`, `codecs.escape_encode`, `codecs.escape_decode` | O(n) | O(n) | As above |
| `codecs.readbuffer_encode(data, errors=None)` | O(n) | O(n) | Copies a buffer to `bytes`, or UTF-8 encodes a `str` |
| `codecs.mbcs_encode`, `codecs.mbcs_decode`, `codecs.oem_encode`, `codecs.oem_decode`, `codecs.code_page_encode`, `codecs.code_page_decode` | O(n) | O(n) | Windows only; the ANSI, OEM and numbered code pages |

### Constants

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `codecs.BOM_UTF8`, `codecs.BOM_UTF16_BE`, `codecs.BOM_UTF16_LE`, `codecs.BOM_UTF32_BE`, `codecs.BOM_UTF32_LE` | O(1) | O(1) | `bytes` constants |
| `codecs.BOM`, `codecs.BOM_BE`, `codecs.BOM_LE`, `codecs.BOM_UTF16`, `codecs.BOM_UTF32` | O(1) | O(1) | `BOM` and the unsuffixed UTF names are in the platform's byte order; `BOM_BE` and `BOM_LE` are the UTF-16 ones |
| `codecs.BOM32_BE`, `codecs.BOM32_LE`, `codecs.BOM64_BE`, `codecs.BOM64_LE` | O(1) | O(1) | Undocumented older names for the UTF-16 and UTF-32 marks |

## Encoding and Decoding

A standard text codec is linear in its input, and so is the output it returns. The same two functions also reach the bytes-to-bytes codecs such as `hex` and
`zlib_codec`, which cost what the module behind them costs.

```python
import codecs

text = "Hello, 世界"
encoded = codecs.encode(text, 'utf-8')  # O(n)
assert encoded == b'Hello, \xe4\xb8\x96\xe7\x95\x8c'
assert codecs.decode(encoded, 'utf-8') == text  # O(n)

# Output length depends on the codec, but stays proportional to the input
assert len(codecs.encode(text, 'utf-16-le')) == 2 * len(text)
assert len(codecs.encode(text, 'utf-32-le')) == 4 * len(text)

# Bytes-to-bytes codecs go through the same functions
assert codecs.encode(b'\x01\xff', 'hex') == b'01ff'
assert codecs.decode(codecs.encode(b'abc' * 100, 'zlib_codec'), 'zlib_codec') == b'abc' * 100
```

### Punycode

`punycode`, the codec behind internationalized domain names, has an encoder that is not linear:
it makes a pass over the input for each distinct non-ASCII character, so its cost is O(n·u) with
u those characters, and O(n²) for varied text. Its decoder inserts each non-ASCII character
into the text built so far, which is O(n²) as well. That is harmless for domain labels, which are
short, and a trap for anything long.

```python
import codecs

label = "bücher"
assert codecs.encode(label, 'punycode') == b'bcher-kva'  # O(n·u)
assert codecs.decode(b'bcher-kva', 'punycode') == label  # O(n²)
assert codecs.encode('bücher.example', 'idna') == b'xn--bcher-kva.example'
```

## The Codec Registry

`lookup()` normalizes the name and consults a cache before anything else, so a repeated lookup is
a dict hit. A name the cache lacks is offered to each search function in registration order, and a
name none of them recognizes is not cached: looking it up again repeats the search.
Unregistering a registered function empties the whole cache.

```python
import codecs

asked = []

def search(name):
    asked.append(name)
    return codecs.lookup('utf-8') if name == 'my_codec' else None

codecs.register(search)  # O(1)
first = codecs.lookup('My-Codec')  # O(r) the first time
assert codecs.lookup('my codec') is first  # O(1): same normalized name, cached
assert asked == ['my_codec']

for _ in range(2):
    try:
        codecs.lookup('no-such-codec')
    except LookupError as error:
        assert 'unknown encoding' in str(error)
    else:
        raise AssertionError('an unknown encoding was found')
assert asked == ['my_codec', 'no_such_codec', 'no_such_codec']  # misses are not cached

codecs.unregister(search)  # O(r), and the cache is emptied
try:
    codecs.lookup('my codec')
except LookupError:
    pass
else:
    raise AssertionError('an unregistered codec was found')

# The helpers are attribute reads on the cached CodecInfo
info = codecs.lookup('utf-8')
assert codecs.getencoder('utf-8') is info.encode
assert codecs.getincrementaldecoder('UTF-8') is info.incrementaldecoder
encode, decode, reader, writer = info  # a CodecInfo unpacks as a 4-tuple
assert info.name == 'utf-8' and reader is codecs.getreader('utf-8')
```

## Incremental Encoding and Decoding

An incremental decoder keeps the bytes of a character split across two chunks and finishes it
with the next call. For UTF-8, UTF-16 and UTF-32 that tail is under four bytes, so decoding a
stream in chunks costs O(n) however the stream is cut. `iterdecode()` and `iterencode()` wrap one
incremental codec in a generator, taking chunks only when you ask for the next result and only
until they produce some output.

```python
import codecs

chunks = [b'caf\xc3', b'\xa9 \xe2\x82', b'\xac']
taken = []

def source():
    for chunk in chunks:
        taken.append(chunk)
        yield chunk

decoded = codecs.iterdecode(source(), 'utf-8')  # O(1) - takes nothing yet
assert taken == []
assert next(decoded) == 'caf'  # the split 'é' waits for its second byte
assert ''.join(decoded) == 'é €'
assert taken == chunks

decoder = codecs.getincrementaldecoder('utf-8')()
assert decoder.decode(b'\xe2\x82') == ''  # O(t + c)
assert decoder.getstate() == (b'\xe2\x82', 0)  # the tail, held for the next call
assert decoder.decode(b'\xac', final=True) == '€'
assert decoder.getstate() == (b'', 0)

encoded = b''.join(codecs.iterencode(['a', 'é'], 'utf-16'))  # O(n) total
assert encoded == codecs.encode('aé', 'utf-16')  # the BOM is written once
```

### UTF-7 Holds the Whole Run

UTF-7 writes non-ASCII text as base64 runs, and its decoder does not emit a run until it has seen
the run's end. Until then the run stays in the tail, and every chunk is joined to it again, so
decoding a long non-ASCII run in chunks is O(n²). A UTF-7 `StreamReader` keeps the same tail and
pays the same cost. Decode UTF-7 in one call where you can.

```python
import codecs

data = codecs.encode('世' * 100, 'utf-7')  # one run: b'+ThZOFk4W...hY-'
decoder = codecs.getincrementaldecoder('utf-7')()

outputs = [decoder.decode(data[start:start + 10]) for start in range(0, 260, 10)]
assert set(outputs) == {''}  # nothing emitted mid-run
assert len(decoder.getstate()[0]) == 260  # O(t + c) per call, and t is the run so far
assert decoder.decode(data[260:], final=True) == '世' * 100

assert codecs.decode(data, 'utf-7') == '世' * 100  # O(n) in one call
```

## Streams

### Reading

`StreamReader.read()` with no arguments decodes the rest of the stream in one step; pass `size`
to take the stream in steps. `chars` only limits what is returned, so on its own it still reads
everything. `readline()` is the expensive one: it refills in pieces and re-splits the line read so
far after each one, so a line of L characters costs O(L²), and each refill also copies whatever
an earlier `read(chars=k)` left buffered. For line-oriented work on long lines, use
`io.TextIOWrapper`, whose `readline()` is linear.

```python
import codecs
import io

raw = io.BytesIO('first line\nsecond ✓\n'.encode('utf-8'))
reader = codecs.getreader('utf-8')(raw)  # O(1) - reads nothing

assert reader.readline() == 'first line\n'  # O(L²) in the line length
assert list(reader) == ['second ✓\n']  # one readline() per line

raw = io.BytesIO(b'abcdefghij')
reader = codecs.getreader('utf-8')(raw)
assert reader.read(4) == 'abcd'  # O(size)
assert raw.tell() == 4
assert reader.read(chars=2) == 'ef'  # reads the rest of the stream into the buffer
assert raw.tell() == 10
assert reader.read() == 'ghij'

# The linear alternative for lines
wrapper = io.TextIOWrapper(io.BytesIO(b'x' * 100_000 + b'\n'), encoding='utf-8')
assert len(wrapper.readline()) == 100_001  # O(L)
```

### Writing

`StreamWriter.write()` encodes its whole argument before one write to the stream.
`writelines()` joins its list first, so it holds the whole batch as one string.

```python
import codecs
import io

raw = io.BytesIO()
writer = codecs.getwriter('utf-16-le')(raw)  # O(1)
writer.write('hé')  # O(n)
writer.writelines(['a', 'b'])  # O(n) - joined into 'ab' first
assert raw.getvalue() == 'héab'.encode('utf-16-le')
```

### codecs.open and EncodedFile

Given an encoding, `codecs.open()` wraps a file opened in binary mode in a `StreamReaderWriter`,
so its reads carry the `readline()` cost above and its newlines are never translated. Python 3.14
deprecates it; the built-in `open()` does the same job with an `io.TextIOWrapper`. `EncodedFile()` wraps a
byte stream in a `StreamRecoder`, which converts in two passes: bytes in one encoding are decoded
and then encoded in the other.

```python
import codecs
import io
import os
import tempfile
import warnings

with tempfile.TemporaryDirectory() as directory:
    path = os.path.join(directory, 'data.txt')
    with open(path, 'wb') as f:
        f.write(b'one\r\ntwo\r\n')

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)  # 3.14+
        with codecs.open(path, encoding='utf-8') as f:  # O(1)
            assert f.read() == 'one\r\ntwo\r\n'  # O(n), newlines untouched
            assert f.encoding == 'utf-8'

    with open(path, encoding='utf-8') as f:
        assert f.read() == 'one\ntwo\n'  # the built-in open() translates them

raw = io.BytesIO()
recoder = codecs.EncodedFile(raw, 'utf-8', 'utf-16-le')  # O(1)
recoder.write('é'.encode('utf-8'))  # O(n): decode UTF-8, encode UTF-16-LE
assert raw.getvalue() == b'\xe9\x00'
raw.seek(0)
assert recoder.read() == b'\xc3\xa9'  # O(n): decode UTF-16-LE, encode UTF-8
```

## Error Handlers

An error handler is called with the exception and returns the replacement and where to resume.
The codec calls it once for each error it reports, so a handler you register adds its own cost
per error on top of the O(n) pass. How much one error covers depends on the codec: the ASCII
encoder reports a whole run of unencodable characters at once, the UTF-16 encoder each lone
surrogate, and the UTF-8 decoder each undecodable sequence. The module-level `*_errors` functions are the built-in
handlers, and each costs the slice it replaces.

```python
import codecs

calls = []

def question_mark(error):
    calls.append((error.start, error.end))
    return '?', error.end

codecs.register_error('question_mark', question_mark)  # O(1)
assert codecs.lookup_error('question_mark') is question_mark  # O(1)

assert codecs.encode('héé€x', 'ascii', 'question_mark') == b'h?x'
assert calls == [(1, 4)]  # one call for the run

calls.clear()
assert codecs.encode('\ud800\ud801', 'utf-16-le', 'question_mark') == b'?\x00?\x00'
assert calls == [(0, 1), (1, 2)]  # one call per lone surrogate

calls.clear()
assert codecs.decode(b'a\xff\xfeb', 'utf-8', 'question_mark') == 'a??b'
assert calls == [(1, 2), (2, 3)]  # one call per undecodable byte

error = UnicodeEncodeError('ascii', 'aé€b', 1, 3, 'ordinal not in range(128)')
assert codecs.xmlcharrefreplace_errors(error) == ('&#233;&#8364;', 3)  # O(f)
assert codecs.backslashreplace_errors(error) == ('\\xe9\\u20ac', 3)
assert codecs.replace_errors(error) == ('??', 3)
assert codecs.ignore_errors(error) == ('', 3)  # O(1)
assert codecs.lookup_error('strict') is codecs.strict_errors
```

## Character Maps

The single-byte code pages are charmap codecs: a 256-entry table to decode, and an encoding table
`charmap_build()` makes from it. Building a table is linear in its entries, and both directions
are linear in the input.

```python
import codecs

decoding_table = 'abc'
encoding_table = codecs.charmap_build(decoding_table)  # O(m)
assert codecs.charmap_encode('cab', 'strict', encoding_table) == (b'\x02\x00\x01', 3)  # O(n)
assert codecs.charmap_decode(b'\x02\x00', 'strict', decoding_table) == ('ca', 2)  # O(n)

assert codecs.make_identity_dict(range(3)) == {0: 0, 1: 1, 2: 2}  # O(m)
# Byte 0x42 decodes to 'A' as well, so 'A' has no single encoding
assert codecs.make_encoding_map({0x41: 0x41, 0x42: 0x41, 0x43: 0x43}) == {0x41: None, 0x43: 0x43}
```

## Common Patterns

### Transcoding a Stream in Chunks

```python
import codecs
import io

source = io.BytesIO('naïve café ✓\n'.encode('utf-8') * 1000)
target = io.BytesIO()

chunks = iter(lambda: source.read(4096), b'')  # O(c) per chunk
text = codecs.iterdecode(chunks, 'utf-8')  # a character cut at a chunk edge is kept
for encoded in codecs.iterencode(text, 'utf-16'):  # O(n) total
    target.write(encoded)

assert target.getvalue() == ('naïve café ✓\n' * 1000).encode('utf-16')
```

### Checking for a Byte Order Mark

```python
import codecs

data = codecs.BOM_UTF8 + 'hello'.encode('utf-8')
if data.startswith(codecs.BOM_UTF8):  # O(1)
    text = data[len(codecs.BOM_UTF8):].decode('utf-8')  # O(n)
assert text == 'hello'
assert codecs.decode(data, 'utf-8-sig') == 'hello'  # the codec that strips it for you
```

## Performance Best Practices

✅ **Do**:

- Use the built-in `open()` for text files: its `readline()` is linear in the line
- Decode a UTF-8, UTF-16 or UTF-32 stream with `iterdecode()` or an incremental decoder, which
  carry a split character over to the next chunk in under four bytes
- Pass `size` to `StreamReader.read()` to take a UTF-8, UTF-16 or UTF-32 stream in steps

❌ **Avoid**:

- `codecs.open()` - deprecated in 3.14, no newline translation, and O(L²) `readline()`
- `StreamReader.read(chars=k)` alone on a large stream - it still reads the whole stream
- Decoding UTF-7 in chunks when the text has long non-ASCII runs - it is O(n²)
- `punycode` on anything longer than a domain label - it is O(n·u), quadratic for varied text

## Version Notes

- **Python 3.14+**: `codecs.open()` is deprecated and emits `DeprecationWarning`; use `open()`
- **All Python 3**: `codecs.open()` with an encoding opens the file in binary mode, so newlines
  are not translated

## Related Modules

- **[io](io.md)** - `TextIOWrapper`, which drives these incremental decoders with a linear `readline()`
- **[encodings](encodings.md)** - the package of codecs the standard search function finds
- **[unicodedata](unicodedata.md)** - normalization and the names `namereplace` writes
- **[base64](base64.md)** - the same transforms as the `base64` codec, as plain functions
