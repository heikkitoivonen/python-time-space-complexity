"""Tests for the announcement bar's rotating question and its dismissal.

The bar asks one of several opening questions and invites a GitHub star. Two
things about it are quiet failures -- the site builds and looks right either
way -- so they are pinned here.

**The question rotates per page.** ``on_page_context`` in
``scripts/mkdocs_hooks.py`` hashes the page URL into an index that
``docs/overrides/main.html`` uses to pick from the locale's ``leads`` list.
Hashing the URL rather than drawing at random keeps the build reproducible:
unchanged content must build to unchanged bytes, or every deploy rewrites
every page and misses every downstream cache.

**Dismissing it has to stick.** Material hides a dismissed banner by storing
``__md_hash`` of its content and hiding the bar again only where that hash
recurs. A rotating question is a different hash on every page, which would
turn one dismissal into a bar that comes straight back -- so
``docs/overrides/partials/javascripts/announce.html`` replaces that check with
one that ignores the content. That override is the only thing standing between
this feature and a bar that cannot be dismissed; delete it and every other
test here still passes.
"""

import collections
import functools
import re
import zlib
from pathlib import Path

import material

import scripts.mkdocs_hooks as hooks

PROJECT_ROOT = Path(__file__).parent.parent
MAIN_HTML = (PROJECT_ROOT / "docs" / "overrides" / "main.html").read_text(encoding="utf-8")
OVERRIDE_PARTIAL = (
    PROJECT_ROOT / "docs" / "overrides" / "partials" / "javascripts" / "announce.html"
)
THEME_PARTIAL = (
    Path(material.__file__).parent / "templates" / "partials" / "javascripts" / "announce.html"
)

# Pages whose URLs the crc32 assertion is spelled out against.
_SAMPLE_SOURCES = {"index.md", "builtins/abs.md", "stdlib/heapq.md"}


def _english_leads() -> list[str]:
    """The `leads` list from the template's `en` announcement entry."""
    import ast

    match = re.search(r"set announcements\s*=\s*(\{.*?\})\s*-?%\}", MAIN_HTML, re.DOTALL)
    assert match, "no `announcements` mapping found in the template"
    return ast.literal_eval(match.group(1))["en"]["leads"]


@functools.lru_cache(maxsize=1)
def _build():
    """The real config and file set, with the config event already run.

    The hook reads more of the config than a stub can plausibly fake -- the
    i18n plugin, the site URL, the alternates -- so run it against the real
    thing rather than a mock that would keep passing after the hook changed.
    """
    from mkdocs.config import load_config
    from mkdocs.structure.files import get_files

    config = load_config(str(PROJECT_ROOT / "mkdocs.yml"))
    config.plugins.run_event("config", config)
    return config, [file for file in get_files(config) if file.src_uri.endswith(".md")]


def _index(file) -> int:
    """Run the hook the way mkdocs would, and return the index it set."""

    class _Page:
        def __init__(self, file):
            self.file = file
            self.url = file.url

    config, _ = _build()
    context = {}
    hooks.on_page_context(context, _Page(file), config, nav=None)
    return context["announce_index"]


def test_the_index_is_a_stable_hash_of_the_url():
    """The builtin `hash` is salted per process; crc32 is not.

    Swapping one for the other looks harmless and passes every other test in
    this file, but it makes each build emit a different question on every
    page -- the exact churn the URL hash exists to avoid.
    """
    _, files = _build()
    sample = [file for file in files if file.src_uri in _SAMPLE_SOURCES]
    assert len(sample) == len(_SAMPLE_SOURCES), f"sample pages missing: {sample}"
    for file in sample:
        assert _index(file) == zlib.crc32(file.url.encode("utf-8")), (
            f"{file.url}: the announce index is no longer a crc32 of the page URL"
        )


def test_pages_do_not_all_draw_the_same_question():
    """The point of the feature: a reader moving between pages sees variety."""
    leads = _english_leads()
    _, files = _build()
    assert len(leads) > 1, "English should offer more than one opening question"
    assert len(files) > len(leads), "too few pages to say anything about the spread"

    drawn = collections.Counter(_index(file) % len(leads) for file in files)
    assert len(drawn) == len(leads), (
        f"only {len(drawn)} of {len(leads)} leads are ever shown: {sorted(drawn)}"
    )
    assert max(drawn.values()) < len(files) / 3, (
        f"one lead covers {max(drawn.values())} of {len(files)} pages"
    )


def test_a_missing_page_context_does_not_break_the_template():
    """Templates rendered outside a page context have no URL to hash.

    The theme renders some of those, and an undefined `announce_index` in the
    modulo would raise rather than degrade -- so the pick carries a default.
    """
    assert re.search(r"\(announce_index \| default\(0\)\) % ", MAIN_HTML), (
        "the lead index must fall back to 0 when no page context exists"
    )


def test_dismissal_ignores_what_the_banner_says():
    """A dismissal has to survive the next page drawing a different question."""
    assert OVERRIDE_PARTIAL.exists(), (
        "the announce partial override is gone; the theme's hash check is back "
        "and dismissing the bar no longer sticks across pages"
    )
    script = OVERRIDE_PARTIAL.read_text(encoding="utf-8")
    body = re.sub(r"\{#-.*?-#\}", "", script, flags=re.DOTALL)
    assert "__md_hash" not in body, (
        "the override must not compare the banner's content hash"
    )
    assert '__md_get("__announce")' in body, "the override must read the stored dismissal"
    assert "hidden" in body, "the override must hide the banner"


def test_the_theme_still_stores_the_dismissal_we_read():
    """Our override reads a value the theme's bundle writes.

    Pinned because a Material upgrade that renames the key or drops the write
    would leave the override reading something nothing sets -- a bar that can
    never be dismissed, on a page that still builds and still looks right.
    """
    assert THEME_PARTIAL.exists(), "the theme no longer ships an announce partial"
    theme = THEME_PARTIAL.read_text(encoding="utf-8")
    assert '__md_get("__announce")' in theme, (
        "the theme's dismissal key changed; the override reads a stale one"
    )
    assert "__md_hash" in theme, (
        "the theme no longer hashes the banner content -- the override may be "
        "unnecessary now, so re-check why it exists before keeping it"
    )
