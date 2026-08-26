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
skips two things we have to supply ourselves: the canonical URL prefix and the
language switcher.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from material.plugins.search import plugin as search_plugin
from mkdocs.plugins import event_priority

# Captured before we start swapping it out, so this survives a reload.
_JIEBA = getattr(search_plugin, "jieba", None)

# Locales whose text jieba should segment.
SEGMENTED_LOCALES = {"zh"}

# locale -> site-root-relative prefix ("/", "/ja/"), filled in by on_config.
_LOCALE_ROOTS: dict[str, str] = {}


def _i18n_config(config: Any) -> Any:
    """The i18n plugin's config, or None when the plugin is not loaded."""
    plugin = config.plugins.get("i18n")
    return plugin.config if plugin is not None else None


def _isolated_locale(config: Any) -> str | None:
    """The locale this pass is building alone, or None for a combined build."""
    i18n = _i18n_config(config)
    return i18n["build_only_locale"] if i18n else None


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
    _LOCALE_ROOTS.clear()
    for language_config in i18n["languages"]:
        _LOCALE_ROOTS[language_config["locale"]] = language_config["link"]

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


@event_priority(-200)
def on_page_context(context: Any, page: Any, config: Any, nav: Any) -> Any:
    """Point the language switcher at the same page, not each locale's home.

    Every locale mirrors the English tree, so a page's path is identical in all
    of them and the equivalent page is just the locale prefix plus that path.
    In a combined build i18n resolves this from the file's real alternates,
    which is more accurate, so we leave that case alone.
    """
    if _isolated_locale(config) is None:
        return context

    for alternate in config.extra.get("alternate", []):
        root = _LOCALE_ROOTS.get(alternate["lang"])
        if root is not None:
            alternate["link"] = f"{root}{page.url}"
    return context
