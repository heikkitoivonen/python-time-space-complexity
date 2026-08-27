# Accessibility

The site targets **WCAG 2.2 Level AA**.

This file records the decisions that got it there and the traps that are easy
to fall back into. Most of them are not obvious from reading the code, which is
why they are written down rather than left to be rediscovered.

`tests/test_accessibility.py` enforces most of what follows, and computes the
contrast ratios from the values actually in the stylesheet - so the numbers
below cannot drift out of date without a test failing.

## Colour

### One token cannot do three jobs

Material derives three different things from a single variable,
`--md-primary-fg-color`:

- the header and tab bar **background**, which white text sits on
- the **link colour** on the white page ground
- the **link colour** on the dark slate ground

The first two want a dark value. The third wants a light one. At Material's
stock `blue` (`#2094f3`) the token satisfies none of them: 3.19:1 in the chrome
and on white, against the 4.5:1 that normal-size text requires.

So the roles are split apart in `docs/stylesheets/extra.css`. Do not collapse
them back into one value, and do not "simplify" the light and dark schemes into
a shared token.

| Token | Light | Dark | Sits on | Ratio |
|---------------------------|-----------|-----------|------------------|--------|
| `--md-primary-fg-color` | `#0b78d2` | `#0b78d2` | white text on it | 4.53:1 |
| `--md-typeset-a-color` | `#0a6cbd` | `#4dabf7` | page / code / tint | ≥4.54:1 |
| `--md-accent-fg-color` | `#3f51d5` | `#8ec5f2` | page ground | ≥6.27:1 |

Link text is deliberately a shade darker than the chrome. That is not an
oversight to be tidied up - see the next rule for why.

### Measure against the surface the colour actually sits on

Links do not only sit on white. On this site they very often sit on:

| Surface | Value |
|-----------------------|-------------------------------------|
| page ground | `#ffffff` |
| inline `code` | `#f5f5f5` |
| admonition tint | base colour at 10% over the ground |

The site uses `warning`, `tip` and `note` heavily, and there are ~300
code-formatted links. A colour measured only against white will pass there and
quietly fail everywhere else: the chrome's `#0b78d2` drops to 4.07-4.17:1 on
those grounds, which is how `--md-typeset-a-color` ended up darker.

Check against **every** admonition type the theme ships, not just the ones the
docs currently use. The tightest are `bug` and `danger`, the two most saturated
tints, and neither appears in the docs today - but a colour tuned only to the
tints in use turns adding a `!!! danger` with a link in it into an accessibility
regression, which is not a trap worth leaving armed. The test reads the tint
list out of the installed theme, so a `mkdocs-material` upgrade that restyles an
admonition is caught too.

### Never dim text with opacity

Material dims inactive nav tabs with `opacity: .7`. At `.7rem` (14px at the
theme's 125% root, so *normal*-size text, not large) over the header that was
2.29:1 - the worst ratio on the site, on the primary navigation of every page.

Opacity is also a colour-only distinction, so it fails SC 1.4.1 independently
of the contrast maths. The selected tab is marked by **weight** instead, and
hover uses a doubled text shadow rather than `font-weight` so the tab strip
does not reflow under the cursor.

If you need to de-emphasise text, change the weight or the colour to a
measured value. Do not reach for `opacity`.

### Re-measure, do not eyeball

`--md-primary-fg-color` is `#0b78d2` because that is the *lightest* colour on
Material blue's own hue that still clears 4.5:1 against white. It measures
**4.53:1** against a 4.5:1 requirement - about 0.03 of headroom.

Any change to it, however small, has to be re-measured. See
[Checking a colour](#checking-a-colour).

## Language

Every page must declare the language it is actually written in.

- **Untranslated pages.** A page with no translation is served from the English
  source under a localized URL, so the document says `lang="fi"` while the body
  is English. A screen reader takes that literally and reads English prose with
  Finnish pronunciation rules, which is not accented English - it is unusable.
  `docs/overrides/main.html` wraps the fallback body in `<div lang="en">`. The
  localized notice stays *outside* that wrapper, because it really is in the
  page language.
- **The language switcher.** Option names are written in the language they
  offer ("Suomi", "简体中文", "日本語") inside a document declared as something
  else. Material emits `hreflang`, which describes the *destination*;
  `docs/overrides/partials/alternate.html` adds `lang`, which is what governs
  pronunciation of the label itself.

That partial is a copy of a generated upstream file. Re-sync it when upgrading
`mkdocs-material`.

## Headings

Heading levels must not skip. The page shape is:

```
## Section
### operation()
#### Time Complexity
```

An `h2` followed directly by an `h4` gives screen-reader users navigating by
heading a phantom level, and they cannot tell whether they missed content.

## Links

- **Anything that opens a new tab needs to say so.** `target="_blank"` with no
  indication means the tab arrives unannounced and the back button stops
  working as expected. The template links carry a localized `aria-label`.
- **`aria-label` replaces the link text, it does not add to it.** A label of
  "opens in a new tab" alone would *destroy* the link's name. The announcement
  bar restates its whole sentence for this reason, and builds both the visible
  markup and the label from one per-locale string set so they cannot drift.

## Adding a locale

Beyond the steps in [TRANSLATING.md](TRANSLATING.md), a new locale needs
accessibility strings or it will silently fall back to English ones:

1. `docs/overrides/main.html` - the announcement-bar string set
   (`lead` / `cta` / `tail` / `newtab`) and the fallback notice, including its
   own `newtab`.
2. `docs/overrides/partials/copyright.html` - the `newtab` entry.
3. `newtab` values carry their own brackets, so each locale keeps its own
   punctuation: halfwidth for `en`/`fi`, fullwidth for `zh`/`ja`.

## Checking a colour

Contrast is cheap to compute and there is no excuse for guessing:

```python
def luminance(hex_colour):
    h = hex_colour.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    a, b = max(a, b), min(a, b)
    return (a + 0.05) / (b + 0.05)


contrast("#0a6cbd", "#f5f5f5")  # 4.95
```

For a colour over a translucent overlay, composite it first:
`fg * alpha + bg * (1 - alpha)` per channel.

Thresholds: **4.5:1** for normal text, **3:1** for large text (24px, or
18.66px bold) and for UI component boundaries. Note that media-query `em`
units are always 16px-based, so Material's `60em` breakpoint is 960px
regardless of the theme's 125% root font size.

## Known gaps

Neither blocks AA conformance:

- **~15 content links** in the docs markdown set `target="_blank"` via
  `attr_list` without an accessible label. They already show a
  `:material-open-in-new:` icon, so the new tab is signalled visually but not
  to a screen reader. Fixing them means editing English pages that have
  translations, so it needs a `--update-hashes` pass.
- **`lang="zh"`** rather than `zh-Hans`. Valid, but it does not say which
  Chinese, so assistive tech and font stacks have to guess.
- **Visited links are undefined.** Material ships no `:visited` rule, so a
  clicked link looks identical to an unclicked one. Not a WCAG failure, but a
  real navigation gap on a reference site this dense with cross-links.

## What static checking cannot tell you

The measurements above come from parsing built HTML and computing colour
values. That is reliable for contrast, language attributes, heading order and
link naming, and silent on everything needing a running browser:

- keyboard traversal order, focus visibility, and focus traps
- how pages actually sound in NVDA, JAWS or VoiceOver
- reflow at 400% zoom (SC 1.4.10) - the wide complexity tables are the thing
  to check
- touch target sizes (SC 2.5.8) on the locale switcher and palette toggle

Treat a clean automated pass as necessary, not sufficient.
