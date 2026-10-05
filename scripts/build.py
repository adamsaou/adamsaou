#!/usr/bin/env python3
"""Render the profile README's SVG assets in the current Caelestia colour scheme.

Usage: python scripts/build.py   (needs `pip install fonttools brotli`)

Colours come from ~/.local/state/caelestia/scheme.json, so re-running this after a
wallpaper change re-themes the README. Rubik is subset and
embedded so the SVGs render identically for everyone.
"""

import base64
import logging
import io
import json
import re
import urllib.request
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / "scripts" / ".cache"
SCHEME = Path.home() / ".local/state/caelestia/scheme.json"

RUBIK_URL = "https://github.com/google/fonts/raw/main/ofl/rubik/Rubik%5Bwght%5D.ttf"
ICON_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/master/"
    "symbols/web/{0}/materialsymbolsrounded/{0}_24px.svg"
)
CHARS = "".join(chr(c) for c in range(32, 127)) + "·—’↗"

# Snapshot of the scheme the README was first built with, used if scheme.json is missing.
FALLBACK = {
    "surface": "130d0b", "surfaceContainerLow": "1a110f", "surfaceContainer": "221714",
    "surfaceContainerHigh": "291d1a", "surfaceContainerHighest": "30231f",
    "onSurface": "f9e0da", "onSurfaceVariant": "bca6a1", "outline": "84716c",
    "outlineVariant": "554440", "primary": "f9b7a6", "onPrimary": "613428",
    "primaryContainer": "764639", "onPrimaryContainer": "ffdbd3",
    "secondaryContainer": "51342d", "onSecondaryContainer": "dfb6ac", "tertiary": "ffe1b3",
    "tertiaryContainer": "f8d291", "onTertiaryContainer": "604613",
}


def load_colours():
    try:
        colours = json.loads(SCHEME.read_text())["colours"]
    except (OSError, KeyError, ValueError):
        colours = {}
    return {k: "#" + colours.get(k, v) for k, v in FALLBACK.items()}


C = load_colours()
logging.getLogger("fontTools").setLevel(logging.ERROR)


def fetch(url, dest):
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url) as r:
            dest.write_bytes(r.read())
    return dest


class Font:
    """A static font face: measures text and embeds itself as a subset woff2."""

    def __init__(self, family, ttfont):
        self.family = family
        opts = Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        sub = Subsetter(opts)
        sub.populate(text=CHARS)
        sub.subset(ttfont)
        self.cmap = ttfont.getBestCmap()
        self.hmtx = ttfont["hmtx"]
        self.upm = ttfont["head"].unitsPerEm
        buf = io.BytesIO()
        ttfont.flavor = "woff2"
        ttfont.save(buf)
        self.data = base64.b64encode(buf.getvalue()).decode()

    def width(self, text, size):
        units = sum(self.hmtx[self.cmap[ord(ch)]][0] for ch in text)
        return units * size / self.upm

    def face(self):
        return f"@font-face{{font-family:{self.family};src:url(data:font/woff2;base64,{self.data}) format('woff2')}}"


def rubik(weight):
    var = TTFont(fetch(RUBIK_URL, CACHE / "Rubik.ttf"))
    return Font(f"rubik{weight}", instantiateVariableFont(var, {"wght": weight}))


SANS = rubik(400)
BOLD = rubik(600)


def icon(name, x, y, size, fill):
    svg = fetch(ICON_URL.format(name), CACHE / "icons" / f"{name}.svg").read_text()
    d = re.search(r'd="([^"]+)"', svg).group(1)
    s = size / 960
    return f'<path transform="translate({x} {y + size}) scale({s})" fill="{fill}" d="{d}"/>'


def text(x, y, s, font, size, fill, anchor="start"):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x}" y="{y}" font-family="{font.family}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}">{s}</text>')


def document(w, h, body, fonts, extra_css=""):
    css = "".join(f.face() for f in fonts) + extra_css
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f"<style>{css}</style>{body}</svg>\n")


def project(name, desc, link):
    W, H = 490, 150
    b = f'<rect width="{W}" height="{H}" rx="28" fill="{C["surfaceContainer"]}"/>'
    b += text(32, 64, name, BOLD, 30, C["onSurface"])
    assert SANS.width(desc, 16) <= W - 64, f"{name}: description too long"
    b += text(32, 94, desc, SANS, 16, C["onSurfaceVariant"])
    b += text(32, 124, link, BOLD, 14, C["primary"])
    b += icon("arrow_outward", 32 + BOLD.width(link, 14) + 4, 110, 16, C["primary"])
    return document(W, H, b, [SANS, BOLD])


def main():
    ASSETS.mkdir(exist_ok=True)
    out = {
        "nook.svg": project("Nook", "A study platform for students and hobbyists.", "nook-study.com"),
        "claven.svg": project("Claven", "A code editor, built from scratch.", "claven.dev"),
    }
    for name, svg in out.items():
        (ASSETS / name).write_text(svg)
        print(f"{name:14} {len(svg) / 1024:6.1f} KiB")


if __name__ == "__main__":
    main()
