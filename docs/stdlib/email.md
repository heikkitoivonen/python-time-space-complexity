# email Module Complexity

The `email` package parses RFC 5322 messages into a tree of `Message` objects and flattens such trees back into text. Nearly all of that work is linear in the text; the exceptions are interpreting a header value, and the work that nesting adds to parsing, flattening and walking a part. A message's headers are stored as the text they came from and interpreted through its *policy* when they are read, so which policy a message carries decides what `msg['To']` costs, and whether it costs that on every access.

## Complexity Reference

Size variables: n = characters or bytes of message text, source parsed or output written, payloads included; L = lines in that text; d = multiparts enclosing a part, its nesting depth; k = parts an operation visits, the whole tree for `walk()` and the direct subparts for `iter_parts()`; h = headers on one message or part; v = characters in one header value; t = tokens that value parses into - words, addresses, comments, encoded words; p = parameters on a MIME header such as Content-Type; P = their total length; c = pieces of one RFC 2231 continued parameter; m = matching headers returned; a = addresses in a list or group; q = defects recorded on one header; ℓ = characters a folded header line may hold, `max_line_length` or `maxlinelen`; f = a handler, factory or encoder the caller supplied, whose cost is its own.

Two policies price every header operation. `compat32`, the default for `Message` and for the `message_from_*()` functions, stores a header value as the string given or read and hands that string back. `EmailPolicy`, the default for `EmailMessage`, parses a value into a header object when code stores it and, for a value read from source, on every fetch, since the parsed object is not kept. The RFC 5322 parser behind it slices the unparsed remainder of the value once per token, and the folder that writes a parsed header back out pops its tokens from the front of a list one at a time, so both are O(v·t) rather than O(v): linear in a value of ordinary length, quadratic in one that runs to thousands of words or addresses. The rows use three letters for the costs that differ between the policies. F is fetching one value: O(v) under `compat32`, a scan for undecodable bytes that returns the stored string itself, and O(v·t) under `EmailPolicy`. S is storing one: O(1) under `compat32`, and O(h + v·t) under `EmailPolicy`, which parses the value and, for a header type that allows only one, scans the existing headers first. W is writing one out. Folded to lines of ℓ, it is O(v) under `compat32`, and under `EmailPolicy` O(v) for an ASCII source value whose lines fit and O(v·t) for one that was stored parsed or has to be refolded. Written as one unbounded line, which `Message.as_string()` does by default, it is O(v·t) under `compat32`, whose folder measures the growing line once per word. Under `EmailPolicy` the line length changes nothing: a source value that is not refolded is copied out in O(v), and a value stored parsed or refolded costs O(v·t), which a non-ASCII value reaches at any line length on every supported release but Python 3.10, unless the policy is `utf8`. In a Space column F is the transient encoded copy the `compat32` scan makes, O(v), or the parsed object `EmailPolicy` builds and returns, O(v + t), and S is O(1) under `compat32` and that parsed object, O(v + t), under `EmailPolicy`.

### Parsing functions

The `email` package's top-level functions, over `email.parser`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `message_from_string(s)` / `message_from_bytes(b)` / `message_from_file(fp)` / `message_from_binary_file(fp)` | O(n + L·d + k·(h + F + v·p)) | O(n) | One `Parser` or `BytesParser` and one parse. Bytes are decoded as ASCII with undecodable bytes surrogate-escaped, a string is copied into a buffer, a file is read in 8 KiB chunks to its end. Header values are stored as source text, whatever the policy; the parser fetches each part's Content-Type, to find nested messages and, through `get_boundary()`, a multipart's boundary parameter, and a multipart's Content-Transfer-Encoding, to check it; under `EmailPolicy` those two are parsed then, and nothing else until fetched. Every body line is matched against the boundary of each multipart enclosing it, which is the L·d term |

### Parser, BytesParser, HeaderParser and BytesHeaderParser

In `email.parser`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Parser()` / `BytesParser()` / `HeaderParser()` / `BytesHeaderParser()` | O(1) | O(1) | `policy=` defaults to `compat32`; `_class=` overrides the policy's `message_factory` |
| `Parser.parse(fp)` / `Parser.parsestr(s)` / `BytesParser.parse(fp)` / `BytesParser.parsebytes(b)` | O(n + L·d + k·(h + F + v·p)) | O(n) | What the functions above call |
| `HeaderParser.parse(fp)` / `HeaderParser.parsestr(s)` / `BytesHeaderParser.parse(fp)` / `BytesHeaderParser.parsebytes(b)` | O(n + h + F) | O(n) | `headersonly` stops interpreting after the headers, but still reads the source to its end and stores the rest as one string payload; a multipart source is not split, so `is_multipart()` is False. To skip the body, stop reading yourself and feed a `FeedParser` |

### FeedParser and BytesFeedParser

In `email.parser`, the incremental interface the others are built on.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `FeedParser()` / `BytesFeedParser()` | O(1) | O(1) | `_factory=` overrides the policy's `message_factory` |
| `FeedParser.feed(data)` / `BytesFeedParser.feed(data)` | O(n + L·d + k·(h + F + v·p)) | O(n) | n, L and the k parts started in this chunk, amortized: the chunk is split at line ends and every complete line is consumed at once, so the cost of the whole message is the same however it is chunked. A part's body lines are kept until the part ends, when they are joined into its payload |
| `FeedParser.close()` / `BytesFeedParser.close()` | O(n + d + h + F) | O(n) | Feeds the final line, ends every open part, checks the root's Content-Type and returns the root; n here is the body of the part the input ended inside, the whole body of a single-part message, joined into its payload now. Adds a `MultipartInvariantViolationDefect` when a `multipart/*` root got no parts |

### Message

In `email.message`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Message()` | O(1) | O(1) | `policy=` defaults to `compat32` |
| `Message[name]` / `Message.get(name)` | O(h + F) | O(F) | Scans the headers case-insensitively for the first match, then fetches it through the policy; None, or `failobj`, when absent |
| `name in Message` / `len(Message)` | O(h) / O(1) | O(1) | `len()` counts headers, duplicates included |
| `Message[name] = value` | O(S) | O(S) | Appends; a header of the same name is not replaced. `compat32` keeps duplicates; `EmailPolicy` raises ValueError for a second Subject, Date, From or any other single-count type. Python 3.14+ raises ValueError for a name outside RFC 5322's field-name characters |
| `del Message[name]` | O(h) | O(h) | Rebuilds the header list without every case-insensitive match; no error when there is none |
| `Message.keys()` / `Message.__iter__` | O(h) | O(h) | The names, duplicates included |
| `Message.values()` / `Message.items()` | O(h·F) | O(h·F) | Every value is fetched through the policy, so under `EmailPolicy` this parses every header |
| `Message.get_all(name)` | O(h + m·F) | O(m·F) | The m matching values, fetched; None when there are none |
| `Message.raw_items()` / `Message.set_raw(name, value)` | O(h) / O(1) | O(h) / O(1) | The stored `(name, value)` pairs as they are, and an append that bypasses the policy |
| `Message.add_header(name, value, **params)` | O(P + S) | O(P + S) | Formats the p keyword parameters, quoting values and RFC 2231-encoding a `(charset, language, value)` tuple, then stores as `Message[name] = value` |
| `Message.replace_header(name, value)` | O(h + S) | O(S) | Replaces the first match in place, keeping its position; KeyError when there is none |
| `Message.get_content_type()` / `Message.get_content_maintype()` / `Message.get_content_subtype()` / `Message.get_content_disposition()` | O(h + F + v) | O(v) | Fetch the Content-Type or Content-Disposition header and read its value up to the first `;` on every call; nothing is cached. `get_content_type()` falls back to `get_default_type()`, and to `text/plain` for a value with no slash |
| `Message.get_content_charset()` / `Message.get_filename()` / `Message.get_boundary()` | O(h + F + v·p) | O(v) | One parameter through `get_param()`; `get_filename()` falls back to the Content-Type `name` parameter |
| `Message.get_params()` / `Message.get_param(param)` | O(h + F + v·p) | O(v) | Split the header value at its semicolons on every call, slicing off the rest of the value once per parameter, which is the v·p; a parameter is returned as a `(charset, language, value)` tuple when it was RFC 2231-encoded, else a string |
| `Message.set_param(param, value)` / `Message.del_param(param)` / `Message.set_boundary(boundary)` | O(h + F + v·p + S) | O(v) | Rebuild the header value with the parameter added, replaced or dropped and store it again; `replace=True` keeps the header's position, otherwise it is deleted and appended. `set_boundary()` raises HeaderParseError when there is no Content-Type header |
| `Message.set_type(type)` | O(p·(h + F + v·p + S)) | O(v) | Replaces the header with the new type and then calls `set_param()` once per parameter the old value had, each rebuilding the header again |
| `Message.get_default_type()` / `Message.set_default_type(ctype)` / `Message.get_unixfrom()` / `Message.set_unixfrom(unixfrom)` / `Message.get_charset()` | O(1) | O(1) | `get_charset()` is the `Charset` a `set_charset()` call stored, not the Content-Type parameter |
| `Message.preamble` / `Message.epilogue` / `Message.defects` | O(1) | O(1) | The text around a multipart's boundaries, and the list the parser appends defects to |
| `Message.get_payload()` | O(h + F + n) | O(n) | Fetches the Content-Transfer-Encoding header, scans the text for undecodable bytes, which encodes it into a transient copy, and returns the stored string itself, not a copy; a payload parsed from bytes that did not decode is re-decoded in the charset parameter, at `get_param()` cost, with replacement characters. On a multipart the subpart list itself, or with `i` its i-th subpart, in O(1) |
| `Message.get_payload(decode=True)` | O(h + F + n) | O(n) | New bytes: the payload decoded from base64, quoted-printable or uuencode, or its bytes as they are under any other encoding; None for a multipart. Undecodable base64 is reported as defects, not raised |
| `Message.set_payload(str)` | O(1) | O(1) | Stores the string itself; no header is touched |
| `Message.set_payload(bytes)` | O(n) | O(n) | Decoded as ASCII with undecodable bytes surrogate-escaped into a new string |
| `Message.set_payload(payload, charset)` / `Message.set_charset(charset)` | O(n + h + F + v·p + S) | O(n) | `set_payload()` encodes the text in the charset first. `set_charset()` adds MIME-Version, sets the Content-Type charset parameter and, when no Content-Transfer-Encoding is set, encodes the payload as the charset's body encoding: base64 for `utf-8`, none for `us-ascii`. `set_charset(None)` deletes the parameter |
| `Message.get_charsets()` | O(k·(d + h + F + v·p)) | O(k) | One `get_content_charset()` per part of `walk()` |
| `Message.attach(payload)` | O(1) | O(1) | Appends the object itself to the subpart list, creating the list from a None payload; TypeError on a string payload. The Content-Type is not changed |
| `Message.is_multipart()` | O(1) | O(1) | True when the payload is a list, whatever the Content-Type says |
| `Message.walk()` | O(k·d) | O(d) | A generator: the message itself, then every part depth-first. Each part is passed up through one generator per level above it, so a deep chain costs more than a flat list of the same parts |
| `Message.as_string()` / `Message.as_bytes()` / `str(Message)` / `bytes(Message)` | O(n·d + k·(h + F + v·p) + h·W) | O(n) | A `Generator` or `BytesGenerator` into a buffer, h and W summed over every part; the n·d is the copy each enclosing multipart makes of its subtree's text, and each multipart reads its boundary parameter. `as_string()` writes headers unfolded unless `maxheaderlen` is given, the O(v·t) case of W; `as_bytes()` folds at the policy's `max_line_length`. A multipart with no boundary parameter gets one generated, after a scan of its flattened parts, and stored on the message |

### EmailMessage and MIMEPart

In `email.message`. `EmailMessage` inherits every `Message` operation with `policy.default` as its policy, so F, S and W take their `EmailPolicy` values. `MIMEPart` is the same class without the `MIME-Version` header, used for subparts.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `EmailMessage()` / `MIMEPart()` | O(1) | O(1) | |
| `EmailMessage.set_content(text)` / `MIMEPart.set_content(text)` | O(n + h + F + v·p + S) + `set_param()` per entry of `params` | O(n + h + S) | Through the policy's `content_manager`, `raw_data_manager` by default: drops the existing Content-* headers, sets Content-Type `text/<subtype>` with the charset parameter, encodes the text and sets Content-Transfer-Encoding. `cte=None` picks 7bit for ASCII text whose lines fit `max_line_length`, 8bit for other text whose lines fit when the policy's `cte_type` allows it, and otherwise quoted-printable or base64 by which is shorter on the first ten lines. `disposition`, `filename` and `cid` each store one more header, `headers` one per entry, and `params` rebuilds Content-Type once per entry. `EmailMessage` adds MIME-Version |
| `EmailMessage.set_content(bytes, maintype, subtype)` | O(n + h + F + v·p + S) + `set_param()` per entry of `params` | O(n + h + S) | As above; `cte` defaults to base64 in lines of `max_line_length` |
| `EmailMessage.set_content(message)` | O(h + F + v·p + S) + `set_param()` per entry of `params` | O(h + S) | Stores the message object itself as the single subpart of a `message/rfc822` part, by reference, so the payload costs nothing beyond the headers rewritten; not copied, and not flattened until the outer message is. Takes the same header options as the text form, at the same cost |
| `EmailMessage.get_content()` / `MIMEPart.get_content()` | O(h + F + v·p + n) | O(n) | `text/*`: the payload decoded from its transfer encoding and then the charset parameter, a new string; `message/rfc822` and `message/external-body`: the stored message itself, in O(h + F); any other `message/*`: the stored message flattened to bytes, at `as_bytes()` cost; anything else: the decoded bytes |
| `EmailMessage.clear()` | O(h + k) | O(1) | Drops every header and the payload; freeing them, when nothing else holds them, costs their size |
| `EmailMessage.clear_content()` | O(h + k) | O(h) | Drops the payload and the Content-* headers, keeping the rest; freeing the payload, when nothing else holds it, costs its size |
| `EmailMessage.make_mixed()` / `EmailMessage.make_alternative()` / `EmailMessage.make_related()` | O(h + F + v·p + S) | O(h) | Splits the headers into Content-* and the rest; when there is content, moves the Content-* headers and the payload, by reference, into a new first subpart. ValueError when the message is already that subtype, or a multipart earlier in the order mixed, alternative, related: `make_mixed()` on an alternative nests it, `make_alternative()` on a mixed raises. The `add_*()` methods convert only when the subtype differs |
| `EmailMessage.add_attachment(*args)` / `EmailMessage.add_alternative(*args)` / `EmailMessage.add_related(*args)` | O(h + F + v·p + S) + `set_content()` | O(h) | Converts with the matching `make_*()` unless already that multipart subtype, builds a new part with `set_content(*args, **kw)` at that row's cost, and attaches it by reference. `add_attachment()` adds a Content-Disposition of `attachment` when the part has none |
| `EmailMessage.get_body(preferencelist)` | O(k·(d + h + F + v·p)) | O(d) | Walks the tree through one generator per level, reading each part's content type and disposition, and a related part's `start` parameter, and returns the best part itself, or None. Returns the same object `walk()` yields |
| `EmailMessage.iter_attachments()` | O(k·(h + F + v·p)) | O(k) | Copies the direct subpart list first, and reads a related message's `start` parameter. Nothing for a non-multipart or a `multipart/alternative`; every part but the root for a `multipart/related`; otherwise every part except the first non-attachment of each body type |
| `EmailMessage.iter_parts()` | O(k) | O(1) | The direct subparts, lazily; nothing for a non-multipart |
| `EmailMessage.is_attachment()` | O(h + F) | O(F) | Whether Content-Disposition is `attachment` |
| `EmailMessage.walk()` / `EmailMessage.defects` / `EmailMessage.preamble` / `EmailMessage.epilogue` | O(k·d) / O(1) | O(d) / O(1) | As on `Message` |
| `EmailMessage.as_string()` / `str(EmailMessage)` | O(n·d + k·(h + F + v·p) + h·W) | O(n) | `maxheaderlen` defaults to the policy's `max_line_length`, so headers are folded; `str()` flattens under `utf8=True`, writing non-ASCII headers as they are |

### Generator, BytesGenerator and DecodedGenerator

In `email.generator`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Generator(outfp)` / `BytesGenerator(outfp)` / `DecodedGenerator(outfp)` | O(1) | O(1) | `mangle_from_` and `maxheaderlen` default to the policy's; `policy=None` means the message's own |
| `Generator.flatten(msg)` / `BytesGenerator.flatten(msg)` | O(n·d + k·(h + F + v·p) + h·W) | O(n) | Writes each part's headers through `policy.fold()`, then its body with line ends converted to the policy's `linesep`; each multipart's boundary is read through `get_boundary()`. Each part's text is buffered and copied into the level above, so a part's text is copied once more per multipart enclosing it. Under `verify_generated_headers` a folded header with a line break that no whitespace follows, or without one at its end, raises HeaderWriteError. `mangle_from_` rewrites body lines that start with `From `. A multipart with no boundary gets one generated and stored, as for `as_string()` |
| `Generator.clone(fp)` | O(1) | O(1) | A generator with the same options writing to `fp`, what `flatten()` uses per subpart |
| `Generator.write(s)` / `BytesGenerator.write(s)` | O(len) | O(len) | `BytesGenerator` encodes as ASCII with surrogate-escaped bytes restored |
| `DecodedGenerator.flatten(msg)` | O(n + h·W + k·(d + h + F + v·p)) | O(n) | Writes the top-level headers, then for every part of `walk()` a text payload as stored, undecoded, or the `fmt` line for a non-text part, with its type and `get_filename()`; multipart parts write nothing |

### Policy, Compat32 and EmailPolicy

In `email.policy`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Compat32(**kw)` / `EmailPolicy(**kw)` | O(1) | O(1) | `Policy` is abstract, so `Policy()` itself raises TypeError, as does an unknown attribute on either; `EmailPolicy` creates a `HeaderRegistry` of its own unless `header_factory` is given. Instances are immutable: assigning an attribute raises AttributeError |
| `Policy.clone(**kw)` / `policy + policy` | O(1) | O(1) | A new policy with the attributes copied and the given ones replaced; `+` applies the right operand's own attribute values over the left's |
| `compat32` / `default` / `strict` / `SMTP` / `SMTPUTF8` / `HTTP` | O(1) | O(1) | Module instances: `strict` is `default` with `raise_on_defect`, `SMTP` with `\r\n` line ends, `SMTPUTF8` also `utf8`, `HTTP` with `\r\n` and no `max_line_length` |
| `Policy.linesep` / `Policy.max_line_length` / `Policy.cte_type` / `Policy.raise_on_defect` / `Policy.mangle_from_` / `Policy.message_factory` / `Policy.verify_generated_headers` / `Compat32.mangle_from_` / `EmailPolicy.refold_source` / `EmailPolicy.utf8` / `EmailPolicy.header_factory` / `EmailPolicy.content_manager` | O(1) | O(1) | `mangle_from_` is True on `compat32` and False on `EmailPolicy`; `verify_generated_headers` is True on both |
| `Policy.handle_defect(obj, defect)` / `Policy.register_defect(obj, defect)` | O(1) | O(1) | `handle_defect()` raises the defect when `raise_on_defect` and otherwise calls `register_defect()`, which appends it to `obj.defects` whatever the policy |
| `Policy.header_max_count(name)` / `EmailPolicy.header_max_count(name)` | O(1) | O(1) | None under `compat32`, the header type's `max_count` under `EmailPolicy`, what `Message[name] = value` checks |
| `Policy.header_source_parse(sourcelines)` / `Compat32.header_source_parse(sourcelines)` / `EmailPolicy.header_source_parse(sourcelines)` | O(v) | O(v) | Joins the source lines into the stored `(name, value)`, stripping the leading whitespace and the trailing line end; the value is not parsed |
| `Policy.header_store_parse(name, value)` / `Compat32.header_store_parse(name, value)` / `EmailPolicy.header_store_parse(name, value)` | O(S) | O(S) | The S of the policy. `EmailPolicy` keeps a header object of that name as it is and raises ValueError for a string containing a line break |
| `Policy.header_fetch_parse(name, value)` / `Compat32.header_fetch_parse(name, value)` / `EmailPolicy.header_fetch_parse(name, value)` | O(F) | O(F) | The F of the policy. `compat32` returns the stored string itself unless it carries undecodable bytes, then a `Header` marked `unknown-8bit`; `EmailPolicy` returns a stored header object as it is and parses a string into a new one |
| `Policy.fold(name, value)` / `Policy.fold_binary(name, value)` / `Compat32.fold(name, value)` / `Compat32.fold_binary(name, value)` / `EmailPolicy.fold(name, value)` / `EmailPolicy.fold_binary(name, value)` | O(W) | O(v) | The W of the policy: `compat32` folds through `Header.encode()`; `EmailPolicy` writes a source string as it is when its lines fit and `refold_source` is `long`, refolds it when they do not or `refold_source` is `all`, and folds a header object from its parse tree. It also refolds any non-ASCII source value, however short, unless the policy is `utf8`; Python 3.10 writes that one out as it is. `fold_binary()` encodes the result, as UTF-8 under `utf8` |

### HeaderRegistry, BaseHeader and the header classes

In `email.headerregistry`, the parsed header objects `EmailPolicy` stores and returns.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `HeaderRegistry()` | O(1) | O(1) | Copies the default name-to-class map; `use_default_map=False` starts empty |
| `HeaderRegistry.map_to_type(name, cls)` | O(1) | O(1) | |
| `HeaderRegistry[name]` | O(1) | O(1) | Builds a new class combining the registered class, `default_class` for an unknown name, with `base_class`, on every lookup |
| `HeaderRegistry(name, value)` | O(v·t) | O(v + t) | Parses the value into a token tree kept on the object, a `BaseHeader`: a `str` subclass holding the unfolded text. The class is the registered one for the name combined with `BaseHeader`: `UnstructuredHeader` / `UniqueUnstructuredHeader` / `DateHeader` / `UniqueDateHeader` / `AddressHeader` / `UniqueAddressHeader` / `SingleAddressHeader` / `UniqueSingleAddressHeader` / `MIMEVersionHeader` / `ParameterizedMIMEHeader` / `ContentTypeHeader` / `ContentDispositionHeader` / `ContentTransferEncodingHeader` / `MessageIDHeader` / `ReferencesHeader`, which supply the parser and properties and are not constructed on their own. Defects found go to the object's `defects`, whatever the policy. `Unique*` types have `max_count` 1; `SingleAddressHeader` raises ValueError when `address` is read with more than one address present |
| `BaseHeader.name` / `BaseHeader.max_count` / `DateHeader.datetime` / `AddressHeader.addresses` / `AddressHeader.groups` / `SingleAddressHeader.address` / `ContentTypeHeader.content_type` / `ContentTypeHeader.maintype` / `ContentTypeHeader.subtype` / `ParameterizedMIMEHeader.params` / `ContentDispositionHeader.content_disposition` / `ContentTransferEncodingHeader.cte` / `MIMEVersionHeader.major` / `MIMEVersionHeader.minor` / `MIMEVersionHeader.version` | O(1) | O(1) | Computed when the header was parsed, except `addresses`, a tuple flattened from `groups` on its first read in O(a) and kept; `params` is a read-only mapping, `datetime` None for an unparsable date |
| `BaseHeader.defects` | O(q) | O(q) | A new tuple of the recorded defects on every read |
| `BaseHeader.fold(policy=policy)` | O(v·t) | O(v) | Refolds the token tree into lines of the policy's `max_line_length`, encoding non-ASCII words as RFC 2047 encoded words unless `utf8` |
| `Address(display_name, username, domain)` | O(v) | O(v) | ValueError for a line break in any part |
| `Address(addr_spec=spec)` | O(v·t) | O(v) | Parses the spec with the header parser instead of taking `username` and `domain`, and raises for anything left over or malformed |
| `Address.display_name` / `Address.username` / `Address.domain` | O(1) | O(1) | |
| `Address.addr_spec` / `str(Address)` | O(v) | O(v) | Built on each read: the local part is quoted when it needs to be, the display name likewise |
| `Group(display_name, addresses)` | O(a) | O(a) | Copies the addresses into a tuple |
| `Group.display_name` / `Group.addresses` / `str(Group)` | O(1) / O(a·v) | O(1) / O(a·v) | |

### ContentManager and raw_data_manager

In `email.contentmanager`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `ContentManager()` / `ContentManager.add_get_handler(key, handler)` / `ContentManager.add_set_handler(typekey, handler)` | O(1) | O(1) | Two dicts: get handlers by content type, maintype or `''`; set handlers by Python type |
| `ContentManager.get_content(msg)` | O(h + F + v + f) | O(f) | Looks the handler up by the full content type, then the maintype, then `''`; KeyError with none |
| `ContentManager.set_content(msg, obj)` | O(h + F + v + f) | O(f) | Reads the content type, TypeError for a multipart message; finds the handler by walking `type(obj)`'s method resolution order, KeyError with none; clears the content headers, then runs it |
| `raw_data_manager` | O(1) | O(1) | The instance behind `policy.default.content_manager`, whose handlers are the `set_content()` and `get_content()` rows above: `str`, `bytes` and `EmailMessage` in, `str`, `bytes` or the message out |

### Header, decode_header and make_header

In `email.header`, the RFC 2047 interface `compat32` folds through.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Header(s, charset)` / `Header.append(s, charset)` | O(v) | O(v) | Each chunk is test-encoded in its charset, bytes decoded first; a chunk that does not fit `us-ascii` is kept as UTF-8, one that does not fit another charset raises UnicodeEncodeError. Consecutive chunks in one charset are merged, joined by a space, when the header is next rendered |
| `Header.encode()` | O(v) | O(v) | Folds the chunks into lines of `maxlinelen` at `splitchars`, each non-ASCII chunk as RFC 2047 encoded words in its charset; O(v·t) with `maxlinelen` 0, one unbounded line, since the line is re-measured at every word; HeaderParseError when the value contains a line break followed by a header-like line |
| `str(Header)` / `Header == other` | O(v) | O(v) | The chunks joined as text |
| `decode_header(header)` | O(v·t) | O(v) | Splits the value into encoded words and plain text and decodes each; consecutive words in one charset are concatenated one at a time, which is the O(v·t). The text stays a string when there is no encoded word at all, and becomes bytes per chunk otherwise |
| `make_header(decoded_seq)` | O(v) | O(v) | A `Header` with one `append()` per chunk |

### Charset

In `email.charset`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Charset(input_charset)` | O(1) | O(1) | Resolves the name through the alias, charset and codec tables; `CharsetError` for a name outside ASCII. An unknown name is accepted, with base64 body encoding, and fails only when it is used to encode. Two charsets with the same input charset compare equal |
| `Charset.input_charset` / `Charset.output_charset` / `Charset.input_codec` / `Charset.output_codec` / `Charset.header_encoding` / `Charset.body_encoding` / `Charset.get_output_charset()` / `Charset.get_body_encoding()` | O(1) | O(1) | `get_body_encoding()` is `base64`, `quoted-printable`, or the `encode_7or8bit()` function for a charset with no body encoding |
| `Charset.header_encode(string)` | O(v) | O(v) | One RFC 2047 encoded word; `SHORTEST` measures both encodings and takes the shorter |
| `Charset.header_encode_lines(string, maxlengths)` | O(v·ℓ) | O(v) | One encoded word per line of the lengths given, re-encoding the line after every character to measure it: linear at RFC line lengths, quadratic for one unbounded line |
| `Charset.body_encode(string)` | O(n) | O(n) | Base64 or quoted-printable per `body_encoding`, else the text re-encoded as ASCII; a new string in every case |
| `add_charset(charset, header_enc, body_enc, output_charset)` / `add_alias(alias, canonical)` / `add_codec(charset, codecname)` | O(1) | O(1) | Module-wide tables, read by every later `Charset()`; `add_charset()` raises ValueError for a `SHORTEST` body encoding |

### encoders

In `email.encoders`, for `Message` payloads under `compat32`; `EmailMessage.set_content()` encodes on its own.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `encode_base64(msg)` / `encode_quopri(msg)` | O(n + h + F + S) | O(n) | Decode the payload through its Content-Transfer-Encoding header, re-encode it and store the text back, then set the header; a second call decodes and re-encodes the same bytes |
| `encode_7or8bit(msg)` | O(n + h + F + S) | O(n) | Decodes the payload to test whether it is ASCII and sets the header to `7bit` or `8bit`; the payload is not changed |
| `encode_noop(msg)` | O(1) | O(1) | |

### iterators

In `email.iterators`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `body_line_iterator(msg, decode=False)` | O(n + k·(d + h + F + v·p)) | O(n) | Lazy: walks the parts, fetches each string payload as it is reached, copies it into a buffer and yields its lines; `decode=True` decodes each payload first, and a decoded payload is bytes, so it yields nothing at all |
| `typed_subpart_iterator(msg, maintype, subtype)` | O(k·(d + h + F + v)) | O(d) | Lazy: the parts of `walk()` whose content maintype, and subtype when given, match |

### MIMEBase, MIMENonMultipart, MIMEMultipart and the MIME types

The `email.mime` package: `email.mime.base`, `email.mime.nonmultipart`, `email.mime.multipart`, `email.mime.text`, `email.mime.application`, `email.mime.image`, `email.mime.audio` and `email.mime.message`. They build `compat32` messages with the headers set in the constructor; `EmailMessage.set_content()` covers the same ground under `policy.default`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `MIMEBase(maintype, subtype, **params)` | O(P + S) | O(P) | Adds Content-Type with the p parameters and MIME-Version; the policy is `compat32` unless given |
| `MIMENonMultipart.attach(payload)` | O(1) | O(1) | Raises MultipartConversionError |
| `MIMEMultipart(subtype, boundary, subparts, **params)` | O(k + P + h + F + v·p + S) | O(k + P) | Attaches each of the k given subparts by reference; a boundary is stored as a Content-Type parameter |
| `MIMEText(text, subtype, charset)` | O(n) | O(n) | `charset=None` encodes the text to test for ASCII: `us-ascii` stored as it is, else `utf-8` stored base64-encoded with the transfer encoding set |
| `MIMEApplication(data, subtype, encoder)` / `MIMEImage(data, subtype, encoder)` / `MIMEAudio(data, subtype, encoder)` | O(n + P + f) | O(n + P) | Store the bytes then run the encoder over them once, `encode_base64()` by default. `MIMEImage` and `MIMEAudio` sniff a `subtype` of None from the leading bytes, in O(1), and raise TypeError when no format is recognised; `MIMEApplication` defaults to `octet-stream` and raises TypeError for None |
| `MIMEMessage(msg, subtype)` | O(S) | O(1) | Attaches the message object itself; TypeError for anything that is not a `Message` |

### utils

In `email.utils`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `parseaddr(addr)` | O(v) | O(v) | A `(realname, address)` pair; `('', '')` for two or more addresses and for most malformed values. `strict=False` restores the lenient parse |
| `getaddresses(fieldvalues)` | O(v) | O(v + a) | Linear in the total length, unlike `AddressHeader`, which parses the same text in O(v·t); the shape to choose for a long recipient list |
| `formataddr(pair)` | O(v) | O(v) | Quotes a display name containing specials; a non-ASCII name becomes an RFC 2047 encoded word in `charset` |
| `parsedate(data)` / `parsedate_tz(data)` / `parsedate_to_datetime(data)` | O(v) | O(v) | None for an unparsable date from the first two, ValueError from the third |
| `formatdate()` / `format_datetime(dt)` / `localtime()` / `mktime_tz(data)` | O(1) | O(1) | |
| `make_msgid()` | O(1) | O(1) | Plus one `socket.getfqdn()` call, a name-service lookup that can block, whenever `domain` is None; pass `domain` to avoid it |
| `quote(s)` / `unquote(s)` / `encode_rfc2231(s)` / `decode_rfc2231(s)` / `collapse_rfc2231_value(value)` | O(v) | O(v) | |
| `decode_params(params)` | O(P + c·log c) | O(P) | Joins the pieces of a continued parameter (`name*0*`, `name*1*`, …) in index order, sorting them, and quotes every plain value |

### errors

In `email.errors`.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `MessageError` / `MessageParseError` / `HeaderParseError` / `BoundaryError` / `MultipartConversionError` / `CharsetError` / `HeaderWriteError` | O(1) | O(1) | Exceptions raised by the operations above; `HeaderParseError` and `BoundaryError` subclass `MessageParseError` |
| `MessageDefect` / `HeaderDefect` / `NoBoundaryInMultipartDefect` / `StartBoundaryNotFoundDefect` / `CloseBoundaryNotFoundDefect` / `FirstHeaderLineIsContinuationDefect` / `MisplacedEnvelopeHeaderDefect` / `MissingHeaderBodySeparatorDefect` / `MultipartInvariantViolationDefect` / `InvalidMultipartContentTransferEncodingDefect` / `InvalidHeaderDefect` / `HeaderMissingRequiredValue` / `NonPrintableDefect` / `ObsoleteHeaderDefect` / `NonASCIILocalPartDefect` / `UndecodableBytesDefect` / `InvalidBase64PaddingDefect` / `InvalidBase64CharactersDefect` / `InvalidBase64LengthDefect` / `InvalidDateDefect` | O(1) | O(1) | The message parser hands each defect it finds to `policy.handle_defect()`: appended to the message's `defects` in O(1) under `compat32` and `default`, raised under `strict`. A header object keeps the defects of its own parse on its `defects`, under every policy. `MessageDefect` subclasses ValueError |

## Fetch a Header Once

Under `policy.default` a header read from source is parsed on every access, and the parse is the expensive part of the whole message. Bind the result once instead of indexing repeatedly.

```python
from email import message_from_string, policy

source = "From: Ann <ann@example.com>\nSubject: Quarterly report\n\nBody\n"

message = message_from_string(source, policy=policy.default)
subject = message["Subject"]  # O(h + v·t): parsed now

print(type(subject).__name__)
print(subject is message["Subject"])  # a second access parses again

legacy = message_from_string(source)  # compat32
print(type(legacy["Subject"]).__name__)
print(legacy["Subject"] is legacy["Subject"])  # the stored string itself
```

Output:

```
_UniqueUnstructuredHeader
False
str
True
```

## Build a Multipart Message

`set_content()` writes the body and its headers. The first `add_attachment()` converts the message to `multipart/mixed`, moving the body text into a new first subpart by reference, and every part it adds is attached the same way; the only copy is the encoding `set_content()` performs.

```python
from email.message import EmailMessage

message = EmailMessage()
message["From"] = "ann@example.com"
message["To"] = "bob@example.com"
message["Subject"] = "Files"
message.set_content("See attached.")  # O(n + h + F + S)

text = message.get_payload()
message.add_attachment(  # O(h + F + v + S), then set_content() on the new part
    b"%PDF-1.4 ...",
    maintype="application",
    subtype="pdf",
    filename="report.pdf",
)

print(message.get_content_type())
print(message.get_body().get_payload() is text)  # moved, not copied
print([part.get_content_type() for part in message.walk()])  # O(k)
print([part.get_filename() for part in message.iter_attachments()])
```

Output:

```
multipart/mixed
True
['multipart/mixed', 'text/plain', 'application/pdf']
['report.pdf']
```

## Stop Reading at the Headers

`HeaderParser` does not save the body: it reads the source to its end and stores the rest as one string. Reading only the headers means stopping the read yourself, which a `FeedParser` allows.

```python
from email.parser import BytesFeedParser, BytesHeaderParser
from email import policy

source = (
    b"Subject: Hello\nContent-Type: multipart/mixed; boundary=B\n\n"
    b"--B\nContent-Type: text/plain\n\nfirst part\n--B--\n"
)

message = BytesHeaderParser(policy=policy.default).parsebytes(source)  # O(n)
print(message.is_multipart(), len(message.get_payload()))

parser = BytesFeedParser(policy=policy.default)
for line in source.splitlines(keepends=True):
    parser.feed(line)  # O(len) per line
    if line == b"\n":
        break  # the body is never fed
headers = parser.close()
print(headers["Subject"], repr(headers.get_payload()))
```

Output:

```
False 47
Hello ''
```

## Version Notes

- **Python 3.11.8+, 3.12.2+ and 3.13+**: `EmailPolicy.fold()` encodes a non-ASCII source header value as RFC 2047 encoded words, unless the policy is `utf8`, instead of writing it out unchanged; that costs O(v·t) rather than O(v). No release of Python 3.10 does it
- **Python 3.11+**: `MIMEImage()` and `MIMEAudio()` recognise the subtype of their data with their own tables; earlier versions use the `imghdr` and `sndhdr` modules, removed in Python 3.13
- **Python 3.13+**, backported to later patch releases of Python 3.10 to 3.12: `parseaddr()` and `getaddresses()` take `strict`, defaulting to True; `Policy.verify_generated_headers` and `HeaderWriteError` guard the generator's output
- **Python 3.14+**: storing a header raises ValueError for a name outside RFC 5322's field-name characters; `localtime()` no longer takes `isdst`

## Related Documentation

- [smtplib Module](smtplib.md) - Sending messages
- [mailbox Module](mailbox.md) - Storing messages
- [base64 Module](base64.md) - The encoding behind base64 transfer encoding
- [quopri Module](quopri.md) - The encoding behind quoted-printable
- [mimetypes Module](mimetypes.md) - Guessing content types from file names
- [html Module](html.md) - Escaping HTML bodies
