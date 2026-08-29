"""Tests for how a per-locale build resolves translated pages.

The hreflang assertions at the bottom are explained in SEO.md.

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


def _resolved_config(locale: str):
    """Run a locale's config event and return the resulting config."""
    from mkdocs.config import load_config

    previous = os.environ.get("BUILD_ONLY_LOCALE")
    os.environ["BUILD_ONLY_LOCALE"] = locale
    try:
        config = load_config(str(PROJECT_ROOT / "mkdocs.yml"))
        config.plugins.run_event("config", config)
        return config
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


def test_hreflang_alternates_are_absolute_urls():
    """hreflang annotations must be fully qualified.

    A relative ``href`` in an hreflang link is not resolved the way a browser
    resolves one, so search engines discard the annotation -- and the markup
    looks perfectly valid either way, which is why this is pinned.
    """
    import scripts.mkdocs_hooks as hooks

    for locale in ["en", *LOCALES]:
        config = _resolved_config(locale)
        alternates = hooks._live_alternates(config)
        assert alternates, f"{locale}: no alternates were configured"
        for alternate in alternates:
            assert alternate["link"].startswith("https://"), (
                f"{locale}: hreflang link {alternate['link']!r} is not absolute"
            )


def test_alternate_rewrite_survives_the_i18n_attribute_shadow():
    """Read the binding Jinja reads, not just the mapping key.

    ``config.extra`` is a UserDict, so ``config.extra.alternate = ...`` binds a
    plain attribute rather than the key, and Jinja resolves attributes first.
    mkdocs-static-i18n rebinds it per page in a combined build, so a rewrite
    that only touched the key would be silently discarded there.
    """
    import scripts.mkdocs_hooks as hooks

    config = _resolved_config("en")
    config.extra["alternate"] = [{"link": "/from-key/", "lang": "en"}]
    assert hooks._live_alternates(config)[0]["link"] == "/from-key/"

    # The ignore is the point of the test: this binds an attribute that is not
    # part of LegacyConfig, exactly as mkdocs-static-i18n does at runtime.
    config.extra.alternate = [  # type: ignore[reportAttributeAccessIssue]
        {"link": "/from-attribute/", "lang": "en"}
    ]
    assert hooks._live_alternates(config)[0]["link"] == "/from-attribute/"


def test_site_origin_ignores_the_per_locale_site_url():
    """An isolated build rewrites site_url to the locale root.

    Joining alternates against that would nest every one of them under
    whichever locale happened to be building.
    """
    import scripts.mkdocs_hooks as hooks

    for locale in LOCALES:
        config = _resolved_config(locale)
        assert hooks._site_origin(config) == "https://pythoncomplexity.com"
