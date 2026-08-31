"""Tests for the render-blocking requests we remove from the critical path.

Five requests blocked first render on every page. Three of them are the
theme's and stay; two were ours, and both are handled by
``scripts/mkdocs_hooks.py`` plus the ``extrahead`` and ``scripts`` blocks in
``docs/overrides/main.html``:

* ``docs/stylesheets/extra.css`` is minified and inlined rather than linked
* the theme's JS bundle is emitted with ``defer``

Roboto is vendored rather than linked from Google, which removes two
third-party origins and a three-hop chain from in front of first paint.

And ``partials/source.html`` drops the attribute that made every page fetch
the repository's star and fork counts from api.github.com.

Each of these is a quiet failure if it regresses -- the site still builds and
still looks right -- so they are pinned here. The reasoning behind each, and
the audits that were deliberately not acted on, are in PERFORMANCE.md.
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


SOURCE_PARTIAL = (PROJECT_ROOT / "docs" / "overrides" / "partials" / "source.html").read_text(
    encoding="utf-8"
)


def test_source_component_is_not_mounted():
    """No `data-md-component="source"` means no api.github.com round trips.

    That one attribute is the whole mechanism: Material's bundle looks for it
    to mount the source component, which fetches the star and fork counts.
    Restoring it silently reintroduces two cross-origin requests per page
    load, and nothing about the rendered page would look different until the
    counts appeared.

    Checked with Jinja comments stripped: the comment there names the
    attribute deliberately, to say what was removed and why.
    """
    markup = re.sub(r"\{#.*?#\}", "", SOURCE_PARTIAL, flags=re.DOTALL)
    assert "data-md-component" not in markup


def test_no_github_api_preconnect():
    """Nothing contacts api.github.com now, so warming it would be waste.

    A preconnect to an origin the page never uses costs a DNS lookup and a TLS
    handshake that nothing consumes.
    """
    markup = re.sub(r"\{#.*?#\}", "", OVERRIDE, flags=re.DOTALL)
    assert "api.github.com" not in markup


def test_source_partial_matches_the_theme_apart_from_that_attribute():
    """Our copy must not drift from the upstream partial it mirrors.

    The theme generates partials/source.html and marks it "do not edit", so a
    release that changes it would leave this override rendering stale markup
    -- a missing icon or class, with no error.
    """
    import material

    theme = (Path(material.__file__).parent / "templates" / "partials" / "source.html").read_text(
        encoding="utf-8"
    )

    def normalise(text: str) -> str:
        text = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
        text = text.replace(' data-md-component="source"', "")
        return re.sub(r"\s+", " ", text).strip()

    assert normalise(SOURCE_PARTIAL) == normalise(theme)


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

    # A specific declaration rather than the first rule in the file, so that
    # reordering extra.css does not fail this for no reason.
    assert "--md-typeset-a-color" in config.extra["inline_css"]
    assert config.extra["bundle_js"].endswith(".min.js")


def test_vendored_fonts_exist_and_are_woff2():
    """Every declared face must be on disk and actually be a font.

    A dead url() in the fonts block does not fail a build or look obviously
    broken -- the browser falls back to a system sans-serif, which most
    readers never consciously notice.
    """
    for face in hooks.FONTS:
        path = PROJECT_ROOT / "docs" / hooks.FONT_DIR / face["file"]
        assert path.is_file(), f"{face['file']} is declared but not vendored"
        assert path.read_bytes()[:4] == b"wOF2", f"{face['file']} is not a woff2"


def test_vendored_fonts_span_every_weight_the_theme_uses():
    """Roboto v51 is variable: one file per style must cover 300/400/700.

    If a future theme release introduced a weight outside the vendored axis
    range, the browser would synthesise it rather than fail, so nothing would
    look broken -- just subtly wrong.
    """
    import material

    theme_css = sorted(Path(material.__file__).parent.rglob("assets/stylesheets/main.*.min.css"))
    used = {int(w) for w in re.findall(r"font-weight:(\d+)", theme_css[0].read_text())}
    assert used, "no font-weight declarations found in the theme stylesheet"

    for face in hooks.FONTS:
        low, high = (int(bound) for bound in face["weight"].split())
        outside = sorted(weight for weight in used if not low <= weight <= high)
        assert not outside, (
            f"{face['file']} has a wght axis of {low}-{high}, but the theme renders {outside}"
        )


def test_fonts_block_still_suppresses_the_theme_default():
    """The whole mechanism is overriding one block by name.

    If mkdocs-material renames or restructures `fonts`, our override stops
    being applied and the Google Fonts stylesheet and its preconnect come
    silently back, undoing this without any visible symptom.
    """
    import material

    base = (Path(material.__file__).parent / "templates" / "base.html").read_text()
    assert "{% block fonts %}" in base, "the theme no longer has a `fonts` block to override"
    assert "fonts.googleapis.com" in base, "the theme no longer links Google Fonts"
    assert "{% block fonts %}" in OVERRIDE, "our override no longer replaces it"


def test_font_preloads_are_crossorigin():
    """Fonts are fetched in CORS mode even same-origin.

    A preload without `crossorigin` is not reused by the font request: the
    file is downloaded twice, so the hint costs a whole extra download rather
    than saving a round trip.
    """
    preloads = re.findall(r'<link rel="preload"[^>]*>', OVERRIDE)
    assert preloads, "no font preload found"
    for tag in preloads:
        assert 'as="font"' in tag and "crossorigin" in tag, tag


def test_no_third_party_font_origin_is_emitted():
    """No markup may reference Google's font origins.

    Checked against the template with its Jinja comments stripped: those
    comments name both origins on purpose, to say what is being replaced.
    """
    markup = re.sub(r"\{#.*?#\}", "", OVERRIDE, flags=re.DOTALL)
    assert "googleapis" not in markup
    assert "gstatic" not in markup
