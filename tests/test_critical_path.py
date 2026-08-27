"""Tests for the render-blocking requests we remove from the critical path.

Five requests blocked first render on every page. Three of them are the
theme's and stay; two were ours, and both are handled by
``scripts/mkdocs_hooks.py`` plus the ``extrahead`` and ``scripts`` blocks in
``docs/overrides/main.html``:

* ``docs/stylesheets/extra.css`` is minified and inlined rather than linked
* the theme's JS bundle is emitted with ``defer``

Plus a ``preconnect`` to api.github.com, measured at 220 ms of LCP. Each of
these is a quiet failure if it regresses -- the site still builds
and still looks right -- so they are pinned here.
"""

import re
from pathlib import Path

import scripts.mkdocs_hooks as hooks

PROJECT_ROOT = Path(__file__).parent.parent
EXTRA_CSS = PROJECT_ROOT / "docs" / "stylesheets" / "extra.css"
OVERRIDE = (PROJECT_ROOT / "docs" / "overrides" / "main.html").read_text(encoding="utf-8")
MKDOCS_YML = (PROJECT_ROOT / "mkdocs.yml").read_text(encoding="utf-8")


def _canonical(css: str) -> str:
    """Strip a stylesheet to the form where only its rules remain."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};:,])\s*", r"\1", css)
    return css.replace(";}", "}").strip()


def test_minify_css_is_lossless():
    """Minifying extra.css must change nothing but whitespace and comments.

    The file carries the site's colour-contrast decisions, so a minifier that
    silently dropped or rewrote a rule would be an accessibility regression
    that no contrast test would catch -- those read the source, not the output.
    """
    source = EXTRA_CSS.read_text(encoding="utf-8")
    assert _canonical(hooks._minify_css(source)) == _canonical(source)


def test_minify_css_preserves_descendant_combinators():
    """A space before `:` is a combinator, and must survive minification.

    `.a :hover` matches a hovered *descendant* of `.a`; `.a:hover` matches `.a`
    itself. Collapsing that space is the one rewrite a naive minifier makes
    that changes which elements a rule applies to.
    """
    assert hooks._minify_css(".a :hover { color: red }") == ".a :hover{color: red}"
    assert hooks._minify_css(".a:hover { color: red }") == ".a:hover{color: red}"


def test_minify_css_keeps_media_query_syntax():
    """`screen and (min-width: 60em)` must not lose the space around `and`."""
    minified = hooks._minify_css("@media screen and (min-width: 60em) { a { b: c } }")
    assert "screen and (min-width: 60em)" in minified


def test_minify_css_actually_shrinks_extra_css():
    """Guard the reason this exists: the file is mostly comments."""
    source = EXTRA_CSS.read_text(encoding="utf-8")
    assert len(hooks._minify_css(source)) < len(source) / 2


def test_extra_css_is_not_also_linked():
    """extra.css is inlined, so a stylesheet link would double-load it.

    `extra_css` in mkdocs.yml would emit exactly the render-blocking <link>
    this change removes, so re-adding it silently undoes the work.
    """
    assert not re.search(r"^extra_css:", MKDOCS_YML, re.MULTILINE)
    assert "<style>{{ config.extra.inline_css | safe }}</style>" in OVERRIDE


def test_github_api_preconnect_is_anonymous():
    """The preconnect must carry `crossorigin`, or it warms the wrong socket.

    Material fetches the repo facts with XMLHttpRequest and leaves
    `withCredentials` false, so those requests are anonymous. A preconnect
    without `crossorigin` opens a credentialed connection that an anonymous
    request may not reuse, which costs a socket instead of saving a round trip
    -- and looks identical in the built HTML unless you know to check.
    """
    assert '<link rel="preconnect" href="https://api.github.com" crossorigin>' in OVERRIDE


def test_bundle_is_deferred():
    assert re.search(r"<script src=\"\{\{ config\.extra\.bundle_js \| url \}\}\" defer>", OVERRIDE)


def test_bundle_js_resolves_to_a_real_theme_asset():
    """The bundle path is derived, not hardcoded -- prove the derivation works.

    base.html hardcodes mkdocs-material's content hash. Copying it into our
    override would 404 on the next upgrade and ship a site with no JavaScript,
    so the hook globs the theme for it; this fails the moment that glob stops
    matching.
    """
    from mkdocs.config import load_config

    config = load_config(str(PROJECT_ROOT / "mkdocs.yml"))
    bundle = hooks._bundle_js(config)

    assert bundle.startswith("assets/javascripts/bundle.")
    assert bundle.endswith(".min.js")
    assert any((Path(directory) / bundle).is_file() for directory in config.theme.dirs), (
        f"{bundle} was derived but exists in none of the theme directories"
    )


def test_on_config_publishes_both_values():
    """main.html reads these off config.extra on every page."""
    from mkdocs.config import load_config

    config = load_config(str(PROJECT_ROOT / "mkdocs.yml"))
    config.plugins.run_event("config", config)

    assert config.extra["inline_css"].startswith(".md-header__source")
    assert config.extra["bundle_js"].endswith(".min.js")
