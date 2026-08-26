"""MkDocs build hooks.

Two unrelated concerns, both driven by which locale is being built.

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
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from material.plugins.search import plugin as search_plugin
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
    """Scope jieba, and restore what i18n skips during an isolated build."""
    language = config.theme["language"] if "language" in config.theme else None
    search_plugin.jieba = _JIEBA if language in SEGMENTED_LOCALES else None

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
    config.extra["alternate"] = [
        {
            "name": language_config["name"],
            "link": language_config["fixed_link"] or language_config["link"],
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
    """Flag fallback pages, and point the language switcher at the same page.

    Every locale mirrors the English tree, so a page's path is identical in all
    of them and the equivalent page is just the locale prefix plus that path.
    In a combined build i18n resolves the switcher from the file's real
    alternates, which is more accurate, so we leave that case alone.
    """
    context["i18n_is_fallback"] = _is_fallback(page, config)

    if _isolated_locale(config) is None:
        return context

    for alternate in config.extra.get("alternate", []):
        root = _LOCALE_ROOTS.get(alternate["lang"])
        if root is not None:
            alternate["link"] = f"{root}{page.url}"
    return context
