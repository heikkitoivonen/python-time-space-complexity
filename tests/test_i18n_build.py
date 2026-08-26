"""Tests for how a per-locale build resolves translated pages.

Production builds one locale at a time (``scripts/build_site.py``), and that
mode has bitten us twice: ``build_only_locale`` makes the locale being built
the *default* one, so mkdocs-static-i18n tags English sources with it and can
no longer tell a translation from a fallback. Both symptoms were invisible to
the rest of the suite -- the sources were fine, only the built site was wrong.
"""

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
LOCALES = ["fi", "ja", "zh"]


def _resolved_files(locale: str):
    """Run a locale's config and file events, returning the surviving Files."""
    from mkdocs.config import load_config
    from mkdocs.structure.files import get_files

    previous = os.environ.get("BUILD_ONLY_LOCALE")
    os.environ["BUILD_ONLY_LOCALE"] = locale
    try:
        config = load_config(str(PROJECT_ROOT / "mkdocs.yml"))
        config.plugins.run_event("config", config)
        return config.plugins.run_event("files", get_files(config), config=config)
    finally:
        if previous is None:
            os.environ.pop("BUILD_ONLY_LOCALE", None)
        else:
            os.environ["BUILD_ONLY_LOCALE"] = previous


def _translated_sources(locale: str) -> list[str]:
    locale_dir = DOCS_DIR / locale
    return sorted(
        page.relative_to(DOCS_DIR).as_posix() for page in locale_dir.rglob("*.md")
    )


@pytest.mark.parametrize("locale", LOCALES)
def test_translations_win_their_url(locale):
    """Every docs/<locale>/ page must be the file served at its URL.

    Regression test: the plugin's tie-break was the last file walked, and
    docs/ is walked alphabetically, so docs/fi/stdlib/ and docs/ja/stdlib/
    lost to docs/stdlib/ and vanished from the site with no warning.
    """
    survivors = {file.src_uri for file in _resolved_files(locale)}
    missing = [page for page in _translated_sources(locale) if page not in survivors]

    assert not missing, (
        f"{locale}: translated pages were dropped in favour of the English "
        f"source: {missing}"
    )


@pytest.mark.parametrize("locale", LOCALES)
def test_fallback_pages_are_flagged(locale):
    """A page with no translation must be flagged so the notice can render.

    Regression test: this was derived from page.file.locale, which equals the
    build locale for every file in a per-locale build, so the untranslated
    notice never rendered on the site that ships.
    """
    import scripts.mkdocs_hooks as hooks

    files = _resolved_files(locale)
    translated = set(_translated_sources(locale))
    pages = [file for file in files if file.src_uri.endswith(".md")]
    assert pages, f"{locale}: no documentation pages resolved"

    class _Page:
        def __init__(self, file):
            self.file = file

    config = type("C", (), {"theme": {"language": locale}})()
    flagged = {
        file.src_uri
        for file in pages
        if hooks._is_fallback(_Page(file), config)
    }

    assert not (flagged & translated), (
        f"{locale}: translated pages wrongly flagged as fallbacks: "
        f"{sorted(flagged & translated)}"
    )
    unflagged_fallbacks = {file.src_uri for file in pages} - flagged - translated
    assert not unflagged_fallbacks, (
        f"{locale}: English fallbacks missing the notice flag: "
        f"{sorted(unflagged_fallbacks)[:5]}"
    )
