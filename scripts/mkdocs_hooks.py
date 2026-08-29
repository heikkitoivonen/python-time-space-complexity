"""MkDocs build hooks.

Three unrelated concerns. The first two are driven by which locale is being
built; the third is the same for every build.

**jieba scoping.** Material's search plugin segments every run of Han
characters with jieba whenever jieba is importable. That is unconditional --
there is no per-locale switch -- and it keys off the Han *script*, so it fires
on Japanese kanji too.

jieba's dictionary is Simplified Chinese, so on Japanese pages it shreds
compounds that are not Chinese words: 組み込み is indexed as 組/み/込/み and
実装 as 実/装, and a reader searching for either finds nothing. Japanese does
not need jieba anyway -- Material loads TinySegmenter in the browser for `ja`.

Measured over this site's Japanese pages, 43 representative queries resolved
28 times with jieba and 40 times without it, so we let jieba run only while
the locale it is meant for is being built.

**Isolated locale builds.** Production builds one self-contained site per
locale (see ``scripts/build_site.py``) so that each gets its own search index
and a reader never lands on a page in a language they cannot read. The i18n
plugin assumes the opposite -- one tree, every locale -- so in that mode it
skips three things we have to supply ourselves: the canonical URL prefix, the
language switcher, and the flag marking a page as an untranslated fallback.
It also mis-resolves which file wins for a page that has a translation, which
``on_files`` below corrects.

**Critical path.** Three things the theme puts in front of first paint are
removed here and in ``docs/overrides/main.html``: our own stylesheet, which is
inlined rather than linked; the theme's JS bundle, which ships without
``defer``; and Roboto, which the theme loads across two third-party origins
and which is vendored instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from material.plugins.search import plugin as search_plugin
from mkdocs.exceptions import PluginError
from mkdocs.plugins import event_priority
from mkdocs.structure.files import Files

# Captured before we start swapping it out, so this survives a reload.
_JIEBA = getattr(search_plugin, "jieba", None)

# Locales whose text jieba should segment.
SEGMENTED_LOCALES = {"zh"}

# locale -> site-root-relative prefix ("/", "/ja/"), filled in by on_config.
_LOCALE_ROOTS: dict[str, str] = {}

# The locale served from the site root, i.e. the one whose pages live at the
# top of docs/ rather than in a subdirectory. Filled in by on_config.
_DEFAULT_LOCALE: str | None = None


# --- Critical path ----------------------------------------------------------
#
# Two of the requests that blocked first render were ours to remove. Both are
# handled here so that docs/overrides/main.html stays declarative.

_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_ADJACENT = re.compile(r"\s*([{};,])\s*")


def _minify_css(css: str) -> str:
    """Strip comments and slack whitespace out of a stylesheet.

    Deliberately conservative: it never touches the space around ``:``,
    because in a selector that space is a descendant combinator -- ``.a
    :hover`` and ``.a:hover`` are different rules -- and telling the two apart
    needs a real parser. Comments are two thirds of extra.css, so the rest is
    not worth the risk of silently rewriting a selector.
    """
    css = _CSS_COMMENT.sub("", css)
    css = re.sub(r"\s+", " ", css)
    css = _CSS_ADJACENT.sub(r"\1", css)
    return css.replace(";}", "}").strip()


def _inline_css(config: Any) -> str:
    """extra.css, minified, for inlining into every page's head.

    It was one render-blocking request for ~700 bytes of gzipped CSS, which
    costs a whole round trip on the critical path. The comments stripped here
    are the record of why each colour is the value it is, so they stay in the
    source file -- which is also what tests/test_accessibility.py reads -- and
    only the built pages lose them.
    """
    source = Path(config.docs_dir) / "stylesheets" / "extra.css"
    return _minify_css(source.read_text(encoding="utf-8"))


# Roboto, self-hosted. Material links it from fonts.googleapis.com, which puts
# a render-blocking stylesheet on a third-party origin in front of the font
# files themselves on a *second* third-party origin -- three hops deep before
# any text can paint in its real face. Serving the files ourselves collapses
# that to one same-origin hop that can be preloaded.
#
# Roboto v51 is a variable font, so one file per (family, style) covers every
# weight Material asks for: 300/400/700 for text, 400/700 for code. The
# `weight` below is the file's own wght axis range, not a single weight.
#
# `latin` is the only subset vendored. Measured across every page in docs/ it
# covers 1,880,111 of 1,880,974 characters. The remainder is ~10 Greek and
# Latin-Extended characters, a few dozen maths arrows, and the CJK and emoji
# that Roboto does not contain at all -- all of which already fall back to a
# system font today and continue to.
#
# Roboto is licensed Apache-2.0; see docs/stylesheets/fonts/LICENSE.txt.
FONT_DIR = "stylesheets/fonts"

FONT_UNICODE_RANGE = (
    "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, "
    "U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, "
    "U+2212, U+2215, U+FEFF, U+FFFD"
)

# Only the upright faces are preloaded: they carry the body text and every
# complexity table, so they are needed on every page. Italics are used by
# prose emphasis and can wait for the cascade to ask for them.
FONTS: tuple[dict[str, Any], ...] = (
    {
        "family": "Roboto", "style": "normal", "weight": "100 900",
        "stretch": "100%", "file": "roboto-v51-latin.woff2", "preload": True,
    },
    {
        "family": "Roboto", "style": "italic", "weight": "100 900",
        "stretch": "100%", "file": "roboto-v51-latin-italic.woff2", "preload": False,
    },
    {
        "family": "Roboto Mono", "style": "normal", "weight": "100 700",
        "stretch": None, "file": "roboto-mono-v51-latin.woff2", "preload": True,
    },
    {
        "family": "Roboto Mono", "style": "italic", "weight": "100 700",
        "stretch": None, "file": "roboto-mono-v51-latin-italic.woff2", "preload": False,
    },
)


def _fonts(config: Any) -> list[dict[str, Any]]:
    """The vendored font faces, each with its path checked.

    A missing file here fails quietly in the worst way: the build succeeds, the
    page renders, and the browser simply falls back to a system sans-serif that
    most readers will not consciously notice. Check at build time instead.
    """
    directory = Path(config.docs_dir) / FONT_DIR
    faces = []
    for face in FONTS:
        if not (directory / face["file"]).is_file():
            raise PluginError(
                f"vendored font missing: {directory / face['file']}. The fonts "
                f"block in docs/overrides/main.html would render a dead url() "
                f"and every page would silently fall back to a system font."
            )
        faces.append({**face, "path": f"{FONT_DIR}/{face['file']}"})
    return faces


def _bundle_js(config: Any) -> str:
    """The theme's hashed JS bundle, as a site-root-relative path.

    base.html hardcodes the current content hash, so overriding its ``scripts``
    block to add ``defer`` means restating the filename -- and a hardcoded hash
    would 404 silently the next time mkdocs-material is upgraded, leaving a
    site with no JavaScript at all. Look it up in the theme instead, and fail
    the build loudly if it ever moves.
    """
    for directory in config.theme.dirs:
        found = sorted(Path(directory).glob("assets/javascripts/bundle.*.min.js"))
        if found:
            return f"assets/javascripts/{found[0].name}"
    raise PluginError(
        "no assets/javascripts/bundle.*.min.js found in the theme: "
        "mkdocs-material's asset layout changed, and the scripts block in "
        "docs/overrides/main.html can no longer resolve the bundle to defer"
    )


def _site_origin(config: Any) -> str | None:
    """The scheme and host of the site, without any path.

    ``config.site_url`` cannot be used directly: an isolated build rewrites it
    to the locale's own root (``https://example.com/fi/``), so joining against
    it would nest every alternate under whichever locale is being built.
    Only the origin is stable across those rewrites.
    """
    if not config.site_url:
        return None
    parts = urlsplit(config.site_url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _absolute_url(origin: str | None, link: str) -> str:
    """Make a site-root-relative link absolute, leaving absolute ones alone.

    hreflang annotations must be fully qualified: a relative ``href`` there is
    not resolved the way it is for a browser, so search engines discard it.
    The links also feed the language switcher, which works either way.

    Idempotent, because the alternates live on ``config.extra`` and are
    rewritten once per page rather than rebuilt.
    """
    if origin is None or link.startswith(("http://", "https://")):
        return link
    return f"{origin}{link}" if link.startswith("/") else f"{origin}/{link}"


def _live_alternates(config: Any) -> list[dict[str, Any]]:
    """The alternates the template will actually render.

    ``config.extra`` is a ``UserDict``, so ``config.extra.alternate = ...``
    binds a plain *attribute* rather than the mapping key -- and Jinja resolves
    attributes before keys, so the attribute wins wherever it exists.
    mkdocs-static-i18n does exactly that once per page in a combined build,
    which silently shadows anything written to the key.

    So read back whichever binding is live, in the same order Jinja does.
    Rewriting the key alone would be discarded in combined builds, and the
    symptom is invisible: valid-looking relative hreflang in the output.
    """
    shadowing = getattr(config.extra, "alternate", None)
    if shadowing is not None:
        return shadowing
    return config.extra.get("alternate", [])


def _i18n_config(config: Any) -> Any:
    """The i18n plugin's config, or None when the plugin is not loaded."""
    plugin = config.plugins.get("i18n")
    return plugin.config if plugin is not None else None


def _isolated_locale(config: Any) -> str | None:
    """The locale this pass is building alone, or None for a combined build."""
    i18n = _i18n_config(config)
    return i18n["build_only_locale"] if i18n else None


def _is_fallback(page: Any, config: Any) -> bool:
    """Is this page the English source standing in for a missing translation?

    ``page.file.locale`` cannot answer this. ``build_only_locale`` makes the
    locale being built the *default* one, so the i18n plugin stamps every file
    in an isolated build with that locale -- English fallbacks included -- and
    a page's locale always equals the build's. The source path still tells the
    truth: a translation lives under ``docs/<locale>/``, a fallback does not.
    """
    language = config.theme["language"] if "language" in config.theme else None
    if language is None or language == _DEFAULT_LOCALE or page is None:
        return False
    return not page.file.src_uri.startswith(f"{language}/")


# Below mkdocs-static-i18n's own -100, so the locale for this pass is already
# applied to the theme and its config normalized by the time we look at it.
@event_priority(-200)
def on_config(config: Any) -> Any:
    """Scope jieba, trim the critical path, and restore what i18n skips."""
    language = config.theme["language"] if "language" in config.theme else None
    search_plugin.jieba = _JIEBA if language in SEGMENTED_LOCALES else None

    # Before the early returns below: these apply to every build, isolated or
    # combined, and main.html reads them out of config.extra on every page.
    config.extra["inline_css"] = _inline_css(config)
    config.extra["bundle_js"] = _bundle_js(config)
    config.extra["fonts"] = _fonts(config)
    config.extra["font_unicode_range"] = FONT_UNICODE_RANGE

    i18n = _i18n_config(config)
    if i18n is None:
        return config

    # `link` is computed from the locale's own `default` flag before
    # build_only_locale rewrites the build flags, so it stays correct here and
    # is the single source of truth for where each locale lives.
    global _DEFAULT_LOCALE
    _LOCALE_ROOTS.clear()
    _DEFAULT_LOCALE = None
    for language_config in i18n["languages"]:
        _LOCALE_ROOTS[language_config["locale"]] = language_config["link"]
        if language_config["link"] == "/":
            _DEFAULT_LOCALE = language_config["locale"]

    locale = _isolated_locale(config)
    if locale is None:
        # Combined build: i18n handles both of the below itself.
        return config

    # An isolated locale is built at the root of its own tree but served from
    # a subdirectory, so mkdocs would otherwise emit canonical URLs missing
    # the locale prefix.
    root = _LOCALE_ROOTS.get(locale, "/")
    if config.site_url:
        config.site_url = urljoin(config.site_url, root)

    # i18n only builds a language switcher when it is building more than one
    # language, which is never true here. It never overwrites a switcher that
    # is already present, so supplying one is enough.
    origin = _site_origin(config)
    config.extra["alternate"] = [
        {
            "name": language_config["name"],
            "link": _absolute_url(
                origin, language_config["fixed_link"] or language_config["link"]
            ),
            "lang": language_config["locale"],
        }
        for language_config in i18n["languages"]
        if language_config["locale"] != "null"
    ]
    return config


# Above mkdocs-static-i18n's -100 so we reorder the file list before it picks
# a winner for each page.
@event_priority(100)
def on_files(files: Any, config: Any) -> Any:
    """Make a locale's own pages outrank the English ones they replace.

    ``build_only_locale`` marks the locale being built as the *default* one,
    so the i18n plugin tags English sources with that locale too and can no
    longer tell a translation from a fallback. Its tie-break is then simply
    the last file it walked, and mkdocs walks ``docs/`` alphabetically -- so a
    translation wins only when its locale directory sorts after the directory
    it mirrors. ``zh`` beats every one; ``docs/fi/stdlib/`` and
    ``docs/ja/stdlib/`` lose to ``docs/stdlib/`` and were dropped silently.

    Sorting the locale's files last makes the tie-break land the right way for
    every locale, whatever it is called. Combined builds resolve this
    correctly on their own, so leave them alone.
    """
    locale = _isolated_locale(config)
    if locale is None or locale == _DEFAULT_LOCALE:
        return files
    prefix = f"{locale}/"
    return Files(sorted(files, key=lambda file: file.src_uri.startswith(prefix)))


@event_priority(-200)
def on_page_context(context: Any, page: Any, config: Any, nav: Any) -> Any:
    """Flag fallback pages, and resolve the alternates for this page.

    The alternates become both the language switcher's links and the page's
    ``hreflang`` annotations, and the latter must be absolute URLs.

    Every locale mirrors the English tree, so a page's path is identical in all
    of them and the equivalent page is just the locale prefix plus that path.
    In a combined build i18n resolves the switcher from the file's real
    alternates, which is more accurate, so we leave that case alone.
    """
    context["i18n_is_fallback"] = _is_fallback(page, config)

    isolated = _isolated_locale(config) is not None
    origin = _site_origin(config)

    for alternate in _live_alternates(config):
        if isolated:
            root = _LOCALE_ROOTS.get(alternate["lang"])
            if root is not None:
                alternate["link"] = f"{root}{page.url}"
        alternate["link"] = _absolute_url(origin, alternate["link"])
    return context
