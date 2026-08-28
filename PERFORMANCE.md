# Performance

This file records why the site loads the way it does, and - just as important -
which reported problems were deliberately left alone.

Most of the decisions below look like things a well-meaning change would undo:
a stylesheet that "should" be a normal `<link>`, fonts that "should" come from
a CDN, a preconnect that "should" be added back. Each one is written down with
the measurement behind it so it does not get re-litigated from scratch.

`tests/test_critical_path.py` enforces the parts that can be checked
statically. Several of them fail silently in the worst way - the site still
builds, still renders, and still looks right - so they are pinned by tests
rather than left to review.

## The critical path

Five requests originally blocked first render. Three were the theme's own;
two were ours. What is left is `main.css` and `palette.css`, both shipped by
`mkdocs-material`.

### Our stylesheet is inlined, not linked

`docs/stylesheets/extra.css` is minified and injected into every page's head
by `scripts/mkdocs_hooks.py`, rather than emitted as a render-blocking `<link>`
by `extra_css`. It was one round trip for about 700 bytes of gzipped CSS.

Two thirds of that file is comments recording why each colour is the value it
is. Those stay in the source - which is also what `tests/test_accessibility.py`
reads - and only the built pages lose them.

**Do not re-add `extra_css` to `mkdocs.yml`.** It emits exactly the `<link>`
this removes, and the page would then carry the CSS twice.

The minifier is deliberately conservative: it never touches the space around
`:`, because in a selector that space is a descendant combinator - `.a :hover`
and `.a:hover` match different elements - and telling the two apart needs a
real parser. Comments are the bulk of the win, so the rest is not worth a
minifier that can silently rewrite which elements a contrast rule applies to.

### The theme bundle is deferred

`docs/overrides/main.html` overrides the theme's `scripts` block to add
`defer`. It is safe because nothing between that tag and `DOMContentLoaded`
needs the bundle: the only inline code touching its globals does so inside a
`DOMContentLoaded` handler, and deferred scripts run before that event fires.

The filename carries the theme's content hash, so the block resolves it by
globbing the installed theme instead of restating the hash. **Do not paste the
hash in.** It would 404 on the next `mkdocs-material` upgrade and ship a site
with no JavaScript at all - which no test and no page would visibly catch.

## Fonts

Roboto and Roboto Mono are vendored in `docs/stylesheets/fonts/`, and
`main.html` overrides the theme's `fonts` block so nothing is fetched from
Google.

The theme's default links a render-blocking stylesheet on
`fonts.googleapis.com` whose only job is to point at woff2 files on
`fonts.gstatic.com`. The real face was three hops deep across two third-party
origins before any text could paint in it, and the files could not be
preloaded because their URLs were not knowable until the second hop resolved.

**Four files, not ten.** Roboto v51 is a variable font, so one file per
(family, style) covers every weight the theme renders - 300/400/700 for text,
400/700 for code. The `font-weight` in each `@font-face` is the file's own
`wght` axis range, not a single weight.

**`latin` only.** Measured across every page in `docs/`, that subset covers
1,880,111 of 1,880,974 characters. The remainder is about ten Greek and
Latin-Extended characters, a few dozen maths arrows, and roughly 19,000 CJK
characters plus emoji that Roboto does not contain at all. Those already fell
back to a system font before this change and still do.

**`crossorigin` on the preloads is required, not decorative.** Fonts are
always fetched in CORS mode, even same-origin. A preload without it is not
reused by the font request, so the file downloads twice - the hint costs an
extra download instead of saving a round trip.

Only the two upright faces are preloaded; they carry the body text and every
complexity table. Italics load on demand.

Roboto is Apache-2.0. The licence ships beside the files.

## No repository facts, and no preconnect for them

`docs/overrides/partials/source.html` drops `data-md-component="source"` from
the theme's partial. That attribute is the entire mechanism: the bundle scans
for it to mount the source component, which fetched the repository's star and
fork counts from `api.github.com` - two cross-origin requests on every page
load, to decorate one footer element.

Nothing visible was lost. The repository icon and name are static template
output; only the counts were script-appended after the round trip.

**There is deliberately no `preconnect` to `api.github.com`.** The page no
longer contacts that origin, and warming a connection nothing opens costs a
DNS lookup and a TLS handshake that nothing consumes. If a report suggests
adding one, the report is describing a page that no longer exists.

## Deliberately not done

Each of these was investigated and rejected. The reasoning is here so the next
person does not repeat the investigation.

| Reported | Why it was left |
|---|---|
| **Cache lifetime (10 min)** | GitHub Pages hardcodes `cache-control: max-age=600` on every response and supports no custom headers. Not fixable while hosting there. The assets are content-hashed and would warrant a year, so the right fix is a CDN in front, not a longer TTL from the origin. |
| **Legacy JavaScript** | `bundle.js` ships prebuilt inside the `mkdocs-material` wheel. There is no JavaScript build in this repo to change. The polyfills are feature-detected, so on a current browser they cost bytes, not execution time. |
| **Unused JavaScript** | Same bundle, same reason. Tree-shaking it means forking the theme. |
| **Unused CSS** | `main.css` is the theme's. Purging it means maintaining a safelist against markup the theme generates at runtime - search results, clipboard tooltips, palette swaps - re-tuned on every upgrade. |
| **Forced reflow** | Traced to the theme's scroll-driven components, reached through the `navigation.tracking` and `navigation.tabs.sticky` features. Removing those would trade real navigation affordances on a 300-page reference site for an unscored diagnostic. |
| **Search index size** | `search_index.json` is about 500 KiB gzipped and is fetched on every page load, not lazily - the theme's gating resolves immediately over http(s). The options that would shrink it, `indexing` and `prebuild_index`, are `Deprecated(message="Unsupported option")` in the community edition. |

## What the audits do not tell you

Only five metrics produce the reported score: FCP, Speed Index, LCP, TBT and
CLS. Everything presented as an "opportunity" or "diagnostic" carries no
weight of its own - it is a hint about what *might* be moving those five.

Two consequences worth remembering:

- A change can clear an audit and move nothing. Cache lifetime is the clearest
  case: it concerns repeat visits, which a cold lab run cannot measure.
- The reverse also holds. Work that shows up in no audit at all can still be
  the thing that matters.

So read the metrics before acting on the audit list. If the metrics are
load-time, the critical path above is where the wins are. If they are TBT, the
suspect is the search index - the theme posts about 6,000 document objects to
its worker, and `postMessage` structured-clones that payload on the main
thread.

## Before changing anything here

- Do not re-add `extra_css`, and do not hardcode the bundle's content hash.
- Do not add a `preconnect` for an origin the page does not contact.
- Do not drop `crossorigin` from a font preload.
- Re-sync `docs/overrides/partials/source.html` when upgrading
  `mkdocs-material`; it mirrors a partial upstream marks "do not edit". A test
  compares the two, modulo the removed attribute.
- Run `make check`. `tests/test_critical_path.py` covers the above.
