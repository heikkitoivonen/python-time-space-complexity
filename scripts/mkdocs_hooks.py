"""MkDocs build hooks.

Material's search plugin segments every run of Han characters with jieba
whenever jieba is importable. That is unconditional -- there is no per-locale
switch -- and it keys off the Han *script*, so it fires on Japanese kanji too.

jieba's dictionary is Simplified Chinese, so on Japanese pages it shreds
compounds that are not Chinese words: 組み込み is indexed as 組/み/込/み and
実装 as 実/装, and a reader searching for either finds nothing. Japanese does
not need jieba anyway -- Material loads TinySegmenter in the browser for `ja`.

Measured over this site's Japanese pages, 43 representative queries resolved
28 times with jieba and 40 times without it, so we let jieba run only while
the locale it is meant for is being built.
"""

from __future__ import annotations

from typing import Any

from material.plugins.search import plugin as search_plugin
from mkdocs.plugins import event_priority

# Captured before we start swapping it out, so this survives a reload.
_JIEBA = getattr(search_plugin, "jieba", None)

# Locales whose text jieba should segment.
SEGMENTED_LOCALES = {"zh"}


# Below mkdocs-static-i18n's own -100, so the locale for this pass is already
# applied to the theme by the time we look at it.
@event_priority(-200)
def on_config(config: Any) -> None:
    """Enable jieba only for the locales that benefit from it.

    mkdocs-static-i18n builds each locale with its own ``build()`` pass, so
    this runs once per locale with ``theme.language`` already set to it.
    """
    language = config.theme["language"] if "language" in config.theme else None
    search_plugin.jieba = _JIEBA if language in SEGMENTED_LOCALES else None
