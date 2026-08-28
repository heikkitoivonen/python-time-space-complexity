# SEO

How the site presents itself to crawlers: hreflang, canonical URLs, sitemaps
and `robots.txt`.

Most of this is generated, and the generated form is easy to get subtly wrong
in ways that still look correct in the markup. hreflang in particular has two
traps that produce valid-looking output which search engines discard, so the
reasoning is written down here rather than left in the diff.

`tests/test_i18n_build.py` enforces the parts that can be checked statically.

## hreflang

Every page carries one `<link rel="alternate" hreflang>` per locale, pointing
at the same page in that locale, and including itself. They are generated in
`scripts/mkdocs_hooks.py` from the same list that feeds the language switcher.

**They must be absolute URLs.** A relative `href` in an hreflang annotation is
not resolved the way a browser resolves one, so a search engine discards it.
The links are otherwise identical either way, which is what makes this easy to
ship broken:

```html
<!-- discarded -->
<link rel="alternate" href="/zh/stdlib/" hreflang="zh">

<!-- honoured -->
<link rel="alternate" href="https://pythoncomplexity.com/zh/stdlib/" hreflang="zh">
```

### `site_url` is not the base to build them from

An isolated locale build rewrites `site_url` to that locale's own root -
`https://pythoncomplexity.com/fi/` - so joining alternates against it nests
every one of them under whichever locale happens to be building, producing
`/fi/zh/stdlib/`. Only the *origin* is stable across that rewrite, so
`_site_origin()` takes scheme and host and discards the path.

### The alternates can be shadowed by an attribute

`config.extra` is a `UserDict`. That makes these two different bindings:

```python
config.extra["alternate"] = [...]   # the mapping key
config.extra.alternate    = [...]   # a plain instance attribute
```

Jinja resolves attributes before keys, so wherever the attribute exists it
wins. mkdocs-static-i18n assigns the attribute form once per page in a
combined build, which silently shadows anything written to the key.

The symptom is nasty: the per-locale builds that ship were correct, because
there the plugin never sets the attribute and Jinja falls through to the key -
while `mkdocs build` and `mkdocs serve` still emitted relative hrefs. So
`_live_alternates()` reads back whichever binding is live, in the same order
Jinja does.

### No `x-default`

Google recommends an `x-default` annotation for the page served when no locale
matches. There is deliberately not one.

The alternates are a single list doing double duty: hreflang annotations *and*
the language switcher, which renders every entry in it as a selectable
language. An `x-default` entry would appear in that dropdown as a language.
Adding one properly means emitting it outside this list, from an overridden
template - worth doing, but it is not a one-line change.

## Canonical URLs

A locale is built at the root of its own tree and served from a subdirectory,
so the hook adds the locale prefix back to `site_url`. Without it every
localized page would claim the English URL as its canonical, which is exactly
the instruction that would drop those pages from the index.

See `TRANSLATING.md`, "One site per locale", for why the build works this way.

## Sitemaps

mkdocs generates one per locale: `/sitemap.xml`, `/fi/sitemap.xml`,
`/zh/sitemap.xml`, `/ja/sitemap.xml`.

Nothing in the site links them and `robots.txt` does not advertise them, so
they are currently discoverable only by being guessed or submitted manually.

If a page-speed trace shows the browser fetching all four, that is the auditing
tool crawling them, not real traffic - no user's browser requests a sitemap.

## robots.txt

`docs/robots.txt` is deliberately permissive:

```
User-agent: *
Allow: /
```

**Known gap:** it carries no `Sitemap:` lines. Adding the four above is the
standard way to make them discoverable, and is the one obvious improvement
available here.

`docs/llms.txt` is a separate, informal convention for describing a site to
language-model crawlers. It is not part of the robots protocol and no crawler
is obliged to read it.

## What static checking cannot tell you

The tests confirm the annotations are absolute, self-referencing, and present
for every locale. They cannot confirm that a search engine agrees: indexing
decisions, whether alternates are treated as a cluster, and whether the
canonical is honoured are all only observable in Search Console, days later.

Treat a clean test run as necessary, not sufficient.
