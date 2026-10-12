#!/usr/bin/env python3
"""Render the profile README's SVG assets in the current Caelestia colour scheme.

Usage:
    uv venv --system-site-packages scripts/.cache/venv
    uv pip install --python scripts/.cache/venv fonttools brotli
    scripts/.cache/venv/bin/python scripts/build.py

Colours are seeded from the primary colour in ~/.local/state/caelestia/scheme.json and
expanded into a dark and a light Material scheme with materialyoucolor (the library
Caelestia itself uses), so the cards follow GitHub's light/dark mode and re-running this
after a wallpaper change re-themes the README. Rubik is subset and embedded so the SVGs
render identically for everyone.
"""

import base64
import logging
import io
import json
import re
import urllib.request
from pathlib import Path

from materialyoucolor.dynamiccolor.material_dynamic_colors import MaterialDynamicColors
from materialyoucolor.hct import Hct
from materialyoucolor.scheme.scheme_tonal_spot import SchemeTonalSpot
from PIL import Image
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / "scripts" / ".cache"
SCHEME = Path.home() / ".local/state/caelestia/scheme.json"

RUBIK_URL = "https://github.com/google/fonts/raw/main/ofl/rubik/Rubik%5Bwght%5D.ttf"
NOOK_ICON_URL = "https://nook-study.com/branding/icon-512.png"
ICON_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/master/"
    "symbols/web/{0}/materialsymbolsrounded/{0}_24px.svg"
)
CHARS = "".join(chr(c) for c in range(32, 127)) + "·—’↗"

# Primary of the scheme the README was first built with, used if scheme.json is missing.
FALLBACK_SEED = "f9b7a6"


def load_seed():
    try:
        return json.loads(SCHEME.read_text())["colours"]["primary"]
    except (OSError, KeyError, ValueError):
        return FALLBACK_SEED


def palette(seed, dark):
    scheme = SchemeTonalSpot(Hct.from_int(int("ff" + seed, 16)), dark, 0.0)
    return {c.name: "#%06x" % (c.get_argb(scheme) & 0xFFFFFF) for c in MaterialDynamicColors().all_colors}


SEED = load_seed()
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


def nook_icon(x, y, size):
    """Nook's app icon from its site, downscaled to 2x and embedded."""
    img = Image.open(fetch(NOOK_ICON_URL, CACHE / "nook-icon.png")).convert("RGB")
    buf = io.BytesIO()
    img.resize((size * 2, size * 2), Image.LANCZOS).save(buf, "PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    return f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="data:image/png;base64,{data}"/>'


def claven_icon(x, y, size):
    """Claven's mark (claven.dev/favicon.svg) on its site background."""
    s = size * 0.55 / 80  # the mark spans 80 units of its 96-unit viewBox
    o = size / 2 - 48 * s
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="#0F1115"/>'
            f'<g transform="translate({x + o:.2f} {y + o:.2f}) scale({s:.4f})">'
            '<path d="M8 8 H62 L34 88 H8 Z" fill="#F5F3EE"/><path d="M72 8 H88 V88 H44 Z" fill="#FF5A2B"/></g>')


def project(slug, name, desc, link, app_icon, C):
    W, H, I = 490, 150, 64
    ix, iy = W - 32 - I, (H - I) // 2
    b = f'<rect width="{W}" height="{H}" rx="28" fill="{C["surfaceContainer"]}"/>'
    b += text(32, 64, name, BOLD, 30, C["onSurface"])
    assert SANS.width(desc, 16) <= ix - 24 - 32, f"{name}: description too long"
    b += text(32, 94, desc, SANS, 16, C["onSurfaceVariant"])
    b += text(32, 124, link, BOLD, 14, C["primary"])
    b += icon("arrow_outward", 32 + BOLD.width(link, 14) + 4, 110, 16, C["primary"])
    b += f'<clipPath id="{slug}-icon"><rect x="{ix}" y="{iy}" width="{I}" height="{I}" rx="16"/></clipPath>'
    b += f'<g clip-path="url(#{slug}-icon)">{app_icon(ix, iy, I)}</g>'
    b += (f'<rect x="{ix + 0.5}" y="{iy + 0.5}" width="{I - 1}" height="{I - 1}" rx="15.5" fill="none" '
          f'stroke="{C["outlineVariant"]}"/>')
    return document(W, H, b, [SANS, BOLD])


def main():
    ASSETS.mkdir(exist_ok=True)
    out = {}
    for mode in "dark", "light":
        C = palette(SEED, mode == "dark")
        out[f"nook-{mode}.svg"] = project("nook", "Nook", "A calm focus app that gets you started.",
                                          "nook-study.com", nook_icon, C)
        out[f"claven-{mode}.svg"] = project("claven", "Claven", "A code editor, built from scratch.",
                                            "claven.dev", claven_icon, C)
    for name, svg in out.items():
        (ASSETS / name).write_text(svg)
        print(f"{name:18} {len(svg) / 1024:6.1f} KiB")


if __name__ == "__main__":
    main()
