"""Regression tests for the WCAG 2.2 AA fixes.

Every test here corresponds to a defect that shipped. The rules they enforce
are documented, with reasoning, in ACCESSIBILITY.md -- this file is the
enforcement, that file is the explanation.

Two things are deliberately derived rather than hard-coded. Contrast is
computed from the values actually in ``docs/stylesheets/extra.css``, so
editing a colour re-runs the maths instead of leaving a stale comment behind.
The surfaces those colours sit on are read from the installed
``mkdocs-material``, so a theme upgrade that changes an admonition tint or the
code background is caught rather than silently invalidating the numbers.

These are source-level checks and run in milliseconds; they do not build the
site. ``tests/test_i18n_build.py`` covers what only the build can show.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_translations import analyze, split_front_matter  # noqa: E402

DOCS_DIR = PROJECT_ROOT / "docs"
EXTRA_CSS = (DOCS_DIR / "stylesheets" / "extra.css").read_text(encoding="utf-8")
OVERRIDES = DOCS_DIR / "overrides"
MAIN_HTML = (OVERRIDES / "main.html").read_text(encoding="utf-8")
COPYRIGHT_HTML = (OVERRIDES / "partials" / "copyright.html").read_text(encoding="utf-8")
ALTERNATE_HTML = (OVERRIDES / "partials" / "alternate.html").read_text(encoding="utf-8")
MKDOCS_YML = (PROJECT_ROOT / "mkdocs.yml").read_text(encoding="utf-8")

# Normal-size text. Large text (24px, or 18.66px bold) needs only 3:1, but
# nothing measured here qualifies -- tab labels are .7rem, which is 14px at
# the theme's 125% root.
AA_NORMAL = 4.5


# --------------------------------------------------------------------------
# colour helpers
# --------------------------------------------------------------------------


def _channels(colour: str) -> tuple[float, ...]:
    value = colour.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(colour: str | tuple[float, ...]) -> float:
    parts = _channels(colour) if isinstance(colour, str) else colour
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground, background) -> float:
    """WCAG 2.x contrast ratio between two opaque colours."""
    high, low = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def composite(overlay: str, base) -> tuple[float, ...]:
    """Flatten an #rrggbbaa overlay onto an opaque base colour."""
    value = overlay.lstrip("#")
    top = tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    alpha = int(value[6:8], 16) / 255 if len(value) == 8 else 1.0
    bottom = _channels(base) if isinstance(base, str) else base
    return tuple(top[i] * alpha + bottom[i] * (1 - alpha) for i in range(3))


def token(selector: str, name: str) -> str:
    """Read a custom property out of a selector block in extra.css."""
    block = re.search(re.escape(selector) + r"\s*\{(.*?)\}", EXTRA_CSS, re.DOTALL)
    assert block, f"extra.css has no `{selector}` block"
    match = re.search(re.escape(name) + r":\s*(#[0-9a-fA-F]{6})", block.group(1))
    assert match, f"`{name}` not set in `{selector}`"
    return match.group(1)


LIGHT = '[data-md-color-scheme="default"]'
DARK = '[data-md-color-scheme="slate"]'
PRIMARY_SELECTOR = '[data-md-color-primary="blue"]'

WHITE = "#ffffff"
# Slate's page ground is hsl(--md-hue 15% 14%) with --md-hue: 225.
SLATE_GROUND = (0.119, 0.126, 0.161)


def _material_css() -> str:
    import material

    found = sorted(Path(material.__file__).parent.rglob("assets/stylesheets/main.*.min.css"))
    if not found:  # pragma: no cover - only if the theme layout changes
        pytest.skip("mkdocs-material stylesheet not found")
    return found[0].read_text(encoding="utf-8")


def light_surfaces() -> dict[str, tuple[float, ...] | str]:
    """Every ground a link sits on in the light scheme.

    Links are not only on the page background: inline `code` puts them on the
    code surface, and an admonition puts them on a tint. A colour checked
    against white alone passes there and fails on all of these.
    """
    css = _material_css()
    surfaces: dict[str, tuple[float, ...] | str] = {"page": WHITE}

    code = re.search(r"--md-code-bg-color:\s*(#[0-9a-fA-F]{6})", css)
    if code:
        surfaces["inline code"] = code.group(1)

    for name, tint in re.findall(
        r"\.md-typeset \.([a-z]+)[,>][^{]{0,80}\{background-color:(#[0-9a-fA-F]{8})", css
    ):
        surfaces[f"{name} admonition"] = composite(tint, WHITE)

    assert len(surfaces) > 3, "no admonition tints parsed from the theme stylesheet"
    return surfaces


# --------------------------------------------------------------------------
# colour contrast
# --------------------------------------------------------------------------


def test_chrome_carries_white_text():
    """Header and tab labels are white on the primary; .7rem is normal text.

    Regression: the stock `blue` (#2094f3) gave 3.19:1 for the active tab and
    2.29:1 for inactive ones -- the worst ratio on the site, on the primary
    navigation of every page.
    """
    primary = token(PRIMARY_SELECTOR, "--md-primary-fg-color")
    ratio = contrast(WHITE, primary)
    assert ratio >= AA_NORMAL, f"white on {primary} is {ratio:.2f}:1, needs {AA_NORMAL}"


@pytest.mark.parametrize("surface", sorted(light_surfaces()))
def test_light_link_clears_aa_on_every_surface(surface):
    """The link colour must clear AA on every ground it can land on.

    Regression: the colour was chosen against white only, and fell to
    4.07-4.17:1 on inline code and admonition tints.
    """
    link = token(LIGHT, "--md-typeset-a-color")
    ground = light_surfaces()[surface]
    ratio = contrast(link, ground)
    assert ratio >= AA_NORMAL, f"link {link} on {surface} is {ratio:.2f}:1"


def test_light_accent_clears_aa():
    """Hover and focus must not be weaker than the resting link colour."""
    accent = token(LIGHT, "--md-accent-fg-color")
    ratio = contrast(accent, WHITE)
    assert ratio >= AA_NORMAL, f"accent {accent} on white is {ratio:.2f}:1"


@pytest.mark.parametrize("name", ["--md-typeset-a-color", "--md-accent-fg-color"])
def test_dark_scheme_link_colours_clear_aa(name):
    """The dark scheme sets its own link colours and must be checked too.

    They are deliberately *not* inherited from the primary: the chrome wants a
    dark value and a link on the slate ground wants a light one.
    """
    colour = token(DARK, name)
    ratio = contrast(colour, SLATE_GROUND)
    assert ratio >= AA_NORMAL, f"{name} {colour} on slate is {ratio:.2f}:1"


def test_link_colour_is_not_inherited_from_the_primary():
    """Collapsing these back into one token is the original defect."""
    for scheme in (LIGHT, DARK):
        block = re.search(re.escape(scheme) + r"\s*\{(.*?)\}", EXTRA_CSS, re.DOTALL)
        assert block, f"extra.css has no `{scheme}` block"
        assert "--md-typeset-a-color" in block.group(1), (
            f"{scheme} must set --md-typeset-a-color explicitly, not inherit the primary"
        )


# --------------------------------------------------------------------------
# opacity is never used to dim text
# --------------------------------------------------------------------------


def test_tab_labels_are_not_dimmed():
    """Material dims inactive tabs to .7; that must be overridden.

    Opacity fails twice over: it drops contrast below AA, and it is a
    colour-only distinction (SC 1.4.1).
    """
    match = re.search(r"\.md-tabs[^{]*\.md-tabs__link\s*\{([^}]*)\}", EXTRA_CSS)
    assert match, "extra.css does not override the tab link opacity"
    assert re.search(r"opacity:\s*1", match.group(1)), "tab labels must render at full opacity"


def test_tab_opacity_override_preserves_the_sticky_animation():
    """The slide-away animation is itself driven by opacity on [hidden].

    An unscoped `opacity: 1` would freeze the sticky tab bar visible.
    """
    match = re.search(r"(\.md-tabs[^{]*)\.md-tabs__link\s*\{[^}]*opacity:\s*1", EXTRA_CSS)
    assert match, "no tab opacity override found"
    assert ":not([hidden])" in match.group(1), (
        "scope the opacity override with :not([hidden]) or the sticky tab bar cannot hide"
    )


def test_selected_tab_is_marked_without_relying_on_colour():
    """SC 1.4.1: the current tab needs a non-colour cue."""
    match = re.search(r"\.md-tabs__item--active[^{]*\{([^}]*)\}", EXTRA_CSS)
    assert match, "no rule marks the active tab"
    assert "font-weight" in match.group(1), "mark the selected tab by weight, not by colour alone"


# --------------------------------------------------------------------------
# search placeholder
# --------------------------------------------------------------------------


def test_search_placeholder_override_is_breakpoint_scoped():
    """Only the desktop placeholder rule may be overridden.

    Regression: Material declares this placeholder three times -- dark grey on
    the white mobile form, white@70% over the header, and transparent while
    the search panel is open. A blanket override made the mobile placeholder
    white on white.
    """
    for match in re.finditer(r"\.md-search__input::placeholder\s*\{", EXTRA_CSS):
        preceding = EXTRA_CSS[: match.start()]
        opened = preceding.rfind("@media")
        assert opened != -1 and preceding.count("{", opened) > preceding.count("}", opened), (
            "the placeholder override must sit inside a min-width media query, or it "
            "also hits the mobile rule and renders white on white"
        )


# --------------------------------------------------------------------------
# language
# --------------------------------------------------------------------------


def _locales_from_mkdocs() -> list[str]:
    return re.findall(r"^\s*- locale:\s*(\S+)\s*$", MKDOCS_YML, re.MULTILINE)


def _jinja_dict(template: str, name: str) -> dict:
    match = re.search(r"set " + name + r"\s*=\s*(\{.*?\})\s*-?%\}", template, re.DOTALL)
    assert match, f"no `{name}` mapping found in the template"
    return ast.literal_eval(match.group(1))


def test_locales_are_discoverable():
    """Guard the parsing the parity tests below depend on."""
    locales = _locales_from_mkdocs()
    assert "en" in locales and len(locales) >= 2, f"unexpected locales: {locales}"


def test_fallback_pages_declare_english():
    """An untranslated page is English prose under a localized `lang`.

    Without the override a screen reader reads it with the page locale's
    pronunciation rules, which is not accented English -- it is unusable.
    """
    assert "i18n_is_fallback" in MAIN_HTML, "the fallback branch is gone"
    assert re.search(r'<div lang="en">\s*\{\{\s*super\(\)\s*\}\}', MAIN_HTML), (
        "the English fallback body must be wrapped in lang=\"en\" (SC 3.1.2)"
    )


def test_fallback_notice_stays_in_the_page_language():
    """The notice really is in the page language, so it belongs outside."""
    wrapper = MAIN_HTML.index('<div lang="en">')
    notice = MAIN_HTML.index("translation-fallback")
    assert notice < wrapper, "the localized notice must not be inside the lang=en wrapper"


def test_language_switcher_declares_its_option_languages():
    """`hreflang` describes the destination; `lang` governs pronunciation."""
    assert 'lang="{{ alt.lang }}"' in ALTERNATE_HTML, (
        "switcher options need lang= as well as hreflang= (SC 3.1.2)"
    )
    assert 'hreflang="{{ alt.lang }}"' in ALTERNATE_HTML, "hreflang must be preserved"


@pytest.mark.parametrize("locale", _locales_from_mkdocs())
def test_every_locale_has_announcement_strings(locale):
    """A missing entry silently falls back to English on a localized page."""
    announcements = _jinja_dict(MAIN_HTML, "announcements")
    assert locale in announcements, f"{locale} missing from the announcement strings"
    assert set(announcements[locale]) == {"lead", "cta", "tail", "newtab"}, (
        f"{locale} announcement entry has the wrong keys"
    )


@pytest.mark.parametrize("locale", [x for x in _locales_from_mkdocs() if x != "en"])
def test_every_translated_locale_has_a_fallback_notice(locale):
    """Only non-default locales can serve a fallback page."""
    notices = _jinja_dict(MAIN_HTML, "fallback_notices")
    assert locale in notices, f"{locale} has no untranslated-page notice"
    assert set(notices[locale]) == {"title", "body", "cta", "newtab"}, (
        f"{locale} notice entry has the wrong keys"
    )


@pytest.mark.parametrize("locale", _locales_from_mkdocs())
def test_every_locale_has_a_footer_new_tab_string(locale):
    newtabs = _jinja_dict(COPYRIGHT_HTML, "newtabs")
    assert locale in newtabs, f"{locale} missing from the footer new-tab strings"


# --------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,template",
    [("main.html", MAIN_HTML), ("copyright.html", COPYRIGHT_HTML)],
)
def test_new_tab_links_carry_an_accessible_label(name, template):
    """target=_blank with no indication: the tab arrives unannounced.

    aria-label *replaces* the link text rather than adding to it, so each
    label has to restate the whole name as well as naming the new tab.
    """
    anchors = re.findall(r"<a\b[^>]*?>", template, re.DOTALL)
    blank = [a for a in anchors if 'target="_blank"' in a]
    assert blank, f"{name}: expected at least one new-tab link"
    unlabelled = [a for a in blank if "aria-label" not in a]
    assert not unlabelled, f"{name}: new-tab link without aria-label: {unlabelled}"


# --------------------------------------------------------------------------
# headings
# --------------------------------------------------------------------------


def _markdown_pages() -> list[Path]:
    return sorted(DOCS_DIR.rglob("*.md"))


@pytest.mark.parametrize(
    "page", _markdown_pages(), ids=lambda p: p.relative_to(DOCS_DIR).as_posix()
)
def test_heading_levels_never_skip(page):
    """`##` straight to `####` gives a phantom level to heading navigation.

    ``analyze`` is reused because it strips fenced code blocks -- a naive scan
    reads ``# comment`` inside a Python example as a level-1 heading.
    """
    _, body = split_front_matter(page.read_text(encoding="utf-8"))
    previous = None
    skips = []
    for level in analyze(body).heading_levels:
        if previous is not None and level > previous + 1:
            skips.append(f"h{previous} -> h{level}")
        previous = level
    assert not skips, f"{page.relative_to(DOCS_DIR)}: heading level skipped: {skips}"


# --------------------------------------------------------------------------
# build configuration
# --------------------------------------------------------------------------


def test_theme_templates_are_not_published_as_pages():
    """custom_dir lives inside docs/, so mkdocs would serve the templates.

    They are fragments with no <html> element and no language, one copy per
    locale.
    """
    match = re.search(r"^exclude_docs:\s*\|?\s*\n((?:\s+\S+\n)+)", MKDOCS_YML, re.MULTILINE)
    assert match, "mkdocs.yml has no exclude_docs block"
    assert "overrides/" in match.group(1), "exclude_docs must cover the overrides/ directory"
