#!/usr/bin/env python3
"""Build one self-contained site per locale.

The i18n plugin's own multi-locale build puts every language in one tree that
shares a single search index. That makes search cross-language: because module
and method names are kept verbatim in every translation, an English search for
``bisect`` or ``deque`` matches the Finnish, Chinese and Japanese pages too --
and matches them in the *title*, which Material boosts by 1000, so they compete
for the top result.

So instead we build each locale separately with ``build_only_locale``, which
produces a complete site for that language alone: translated pages where they
exist, English fallbacks everywhere else, and its own search index containing
only those. The default locale goes to the site root and the rest into their
own subdirectories, which reproduces the same URL layout as before.

Usage::

    python scripts/build_site.py                  # every locale
    python scripts/build_site.py en ja            # just these
    python scripts/build_site.py --strict         # extra args go to mkdocs
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

import yaml
from mkdocs.utils.yaml import get_yaml_loader, yaml_load

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "mkdocs.yml"


def locales() -> list[tuple[str, str]]:
    """Return (locale, link) pairs from mkdocs.yml, default locale first.

    The default locale has to be built first: it is the one that owns the site
    root, and mkdocs empties the output directory it is given, which would wipe
    the other locales' subdirectories if it ran afterwards.
    """
    # mkdocs' loader understands the !ENV and !!python/name: tags this config
    # uses. yaml_load is annotated to take a BaseLoader subclass, but PyYAML's
    # Loader (what get_yaml_loader builds on) is a sibling of BaseLoader rather
    # than a subclass, so the annotation cannot express what it returns.
    loader = cast("type[yaml.BaseLoader]", get_yaml_loader())
    with CONFIG_FILE.open("rb") as handle:
        config = yaml_load(handle, loader)

    for plugin in config.get("plugins", []):
        if isinstance(plugin, dict) and "i18n" in plugin:
            languages = plugin["i18n"]["languages"]
            break
    else:
        raise SystemExit("No i18n plugin configured in mkdocs.yml")

    found = [
        (
            language["locale"],
            language.get("link") or ("/" if language.get("default") else f"/{language['locale']}/"),
        )
        for language in languages
        if language["locale"] != "null"
    ]
    # Default locale (link "/") first; the rest keep their configured order.
    return sorted(found, key=lambda pair: pair[1] != "/")


def _run_mkdocs(locale: str, target: Path, extra: list[str]) -> None:
    subprocess.run(
        ["uv", "run", "mkdocs", "build", "-d", str(target), *extra],
        cwd=PROJECT_ROOT,
        env={**os.environ, "BUILD_ONLY_LOCALE": locale},
        check=True,
        stdout=subprocess.DEVNULL,
    )


def build(locale: str, link: str, site_dir: Path, extra: list[str], preserve: set[str]) -> float:
    """Build one locale into site_dir. Returns elapsed seconds.

    ``preserve`` names sibling locale directories that must survive. It matters
    only for the default locale, which builds into the site root: mkdocs empties
    the directory it is given, so building it in place would delete the other
    locales sitting inside it. Building elsewhere and merging avoids that, so a
    partial build never destroys a locale it was not asked to touch.
    """
    target = site_dir if link == "/" else site_dir / link.strip("/")
    print(f"  {locale:<4} -> {target.relative_to(PROJECT_ROOT)}", flush=True)
    started = time.monotonic()

    if target != site_dir or not preserve:
        _run_mkdocs(locale, target, extra)
        return time.monotonic() - started

    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as staging_name:
        staging = Path(staging_name)
        _run_mkdocs(locale, staging, extra)
        site_dir.mkdir(exist_ok=True)
        for existing in site_dir.iterdir():
            if existing.name in preserve:
                continue
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
        for produced in staging.iterdir():
            shutil.move(str(produced), str(site_dir / produced.name))
    return time.monotonic() - started


def main(argv: list[str]) -> int:
    wanted = [arg for arg in argv if not arg.startswith("-")]
    extra = [arg for arg in argv if arg.startswith("-")]

    available = locales()
    known = {locale for locale, _ in available}
    for locale in wanted:
        if locale not in known:
            raise SystemExit(f"Unknown locale '{locale}'. Known: {', '.join(sorted(known))}")
    selected = [pair for pair in available if not wanted or pair[0] in wanted]

    site_dir = PROJECT_ROOT / "site"
    # Only a full build owns the whole tree; a partial one must leave the
    # locales it is not rebuilding in place.
    if not wanted and site_dir.exists():
        shutil.rmtree(site_dir)

    rebuilding = {link.strip("/") for _, link in selected if link != "/"}
    preserve = (
        {
            link.strip("/")
            for _, link in available
            if link != "/" and link.strip("/") not in rebuilding
        }
        if wanted
        else set()
    )

    print(f"Building {len(selected)} locale(s), each self-contained:")
    total = 0.0
    for locale, link in selected:
        total += build(locale, link, site_dir, extra, preserve)
    if preserve & {p.name for p in site_dir.iterdir() if p.is_dir()}:
        kept = sorted(preserve & {p.name for p in site_dir.iterdir() if p.is_dir()})
        print(f"Kept existing build(s) for: {', '.join(kept)}")
    print(f"Done in {total:.0f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
