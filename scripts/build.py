#!/usr/bin/env python3
"""Render the profile README's SVG assets in the current Caelestia colour scheme.

Usage: python scripts/build.py   (needs `pip install fonttools brotli`)

Colours come from ~/.local/state/caelestia/scheme.json, so re-running this after a
wallpaper change re-themes the README. Fonts (Rubik + CaskaydiaCove) are subset and
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
MONO_PATH = Path("/usr/share/fonts/TTF/CaskaydiaCoveNerdFontMono-Regular.ttf")
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
MONO = Font("mono", TTFont(MONO_PATH))


def icon(name, x, y, size, fill):
    svg = fetch(ICON_URL.format(name), CACHE / "icons" / f"{name}.svg").read_text()
    d = re.search(r'd="([^"]+)"', svg).group(1)
    s = size / 960
    return f'<path transform="translate({x} {y + size}) scale({s})" fill="{fill}" d="{d}"/>'


def text(x, y, s, font, size, fill, anchor="start"):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x}" y="{y}" font-family="{font.family}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}">{s}</text>')


def chip(x, y, label, font, size, fill, fg, h=30, pad=14, dot=None):
    """Pill with vertically centred label. Returns (svg, width)."""
    lead = 14 if dot else 0
    w = font.width(label, size) + pad * 2 + lead
    out = f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" fill="{fill}"/>'
    if dot:
        out += f'<circle cx="{x + pad + 3}" cy="{y + h / 2}" r="3.5" fill="{dot}"/>'
    out += text(f"{x + pad + lead:.1f}", f"{y + h / 2 + size * 0.36:.1f}", label, font, size, fg)
    return out, w


def chips(x, y, labels, font, size, fill, fg, gap=8, **kw):
    out = ""
    for label in labels:
        svg, w = chip(x, y, label, font, size, fill, fg, **kw)
        out += svg
        x += w + gap
    return out, x - gap


def wrap(s, font, size, width):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if font.width(trial, size) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def document(w, h, body, fonts, extra_css=""):
    css = "".join(f.face() for f in fonts) + extra_css
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f"<style>{css}</style>{body}</svg>\n")


def fits(label, font, size, width):
    assert font.width(label, size) <= width, f"{label!r} overflows {width}px"


def header():
    W, H = 1000, 320
    b = f'<rect width="{W}" height="{H}" rx="32" fill="{C["surface"]}"/>'

    # Vertical bar, like the Caelestia shell's.
    b += f'<rect x="16" y="16" width="56" height="{H - 32}" rx="28" fill="{C["surfaceContainerLow"]}"/>'
    b += f'<circle cx="44" cy="52" r="20" fill="{C["primaryContainer"]}"/>'
    b += icon("electric_bolt", 32, 40, 24, C["onPrimaryContainer"])
    b += f'<rect x="24" y="92" width="40" height="136" rx="20" fill="{C["surfaceContainer"]}"/>'
    for i in range(5):
        b += f'<circle cx="44" cy="{112 + i * 24}" r="3.5" fill="{C["outlineVariant"]}"/>'
    b += f'<rect class="ws" x="38" y="98" width="12" height="28" rx="6" fill="{C["primary"]}"/>'
    b += text(44, 264, "17", MONO, 15, C["onSurfaceVariant"], "middle")
    b += text(44, 284, "21", MONO, 15, C["onSurfaceVariant"], "middle")

    # Main panel.
    b += f'<rect x="88" y="16" width="896" height="{H - 32}" rx="28" fill="{C["surfaceContainer"]}"/>'
    x = 128
    svg, _ = chip(x, 48, "adam saoudani · morocco", MONO, 14, C["secondaryContainer"],
                  C["onSecondaryContainer"], dot=C["primary"])
    b += svg
    b += text(x - 4, 160, "eleco", BOLD, 92, C["onSurface"])
    tagline = "student dev building games, web apps & robots"
    fits(tagline, SANS, 19, 510)
    b += text(x, 200, tagline, SANS, 19, C["onSurfaceVariant"])
    b += text(x, 255, "now building", MONO, 13, C["outline"])
    nx = x + MONO.width("now building", 13) + 14
    svg, w = chip(nx, 235, "nook", BOLD, 15, C["primary"], C["onPrimary"], h=30, pad=16)
    b += svg
    svg, _ = chip(nx + w + 8, 235, "claven", BOLD, 15, C["tertiaryContainer"], C["onTertiaryContainer"], h=30, pad=16)
    b += svg

    # Right tile: a few facts, laid out like dashboard rows.
    tx, ty, tw, th = 664, 40, 296, H - 80
    b += f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="22" fill="{C["surfaceContainerHigh"]}"/>'
    rows = [
        ("electric_bolt", C["tertiary"], "minato", "the yellow flash, my favourite"),
        ("battery_charging_full", C["primary"], "monster energy", "my fuel of choice"),
        ("theater_comedy", C["onSecondaryContainer"], "acting · mun · sports", "when i'm not coding"),
    ]
    for i, (name, tint, title, sub) in enumerate(rows):
        cy = ty + th * (2 * i + 1) / 6
        b += f'<circle cx="{tx + 44}" cy="{cy}" r="22" fill="{C["surfaceContainerHighest"]}"/>'
        b += icon(name, tx + 32, cy - 12, 24, tint)
        fits(sub, SANS, 14, tw - 92)
        b += text(tx + 80, cy - 3, title, BOLD, 16, C["onSurface"])
        b += text(tx + 80, cy + 17, sub, SANS, 14, C["onSurfaceVariant"])

    css = (".ws{animation:ws 12s cubic-bezier(.3,0,0,1) infinite}"
           "@keyframes ws{0%,20%{transform:translateY(0)}25%,45%{transform:translateY(48px)}"
           "50%,70%{transform:translateY(24px)}75%,95%{transform:translateY(72px)}100%{transform:translateY(0)}}"
           "@media (prefers-reduced-motion:reduce){.ws{animation:none}}")
    return document(W, H, b, [SANS, BOLD, MONO], css)


def project(name, kind, icon_name, accent, on_accent, status, desc, tags, link):
    W, H = 490, 232
    b = f'<rect width="{W}" height="{H}" rx="28" fill="{C["surfaceContainer"]}"/>'
    b += f'<rect x="28" y="28" width="56" height="56" rx="18" fill="{accent}"/>'
    b += icon(icon_name, 40, 40, 32, on_accent)
    b += text(102, 60, name, BOLD, 28, C["onSurface"])
    b += text(102, 80, kind, MONO, 13, C["outline"])

    sw = MONO.width(status, 12) + 28 + 14
    svg, _ = chip(W - 28 - sw, 31, status, MONO, 12, C["surfaceContainerHighest"],
                  C["onSurfaceVariant"], h=26, dot=accent)
    b += svg

    lines = wrap(desc, SANS, 16, W - 56)
    assert len(lines) <= 2, f"{name}: description wraps to {len(lines)} lines"
    for i, line in enumerate(lines):
        b += text(28, 126 + i * 24, line, SANS, 16, C["onSurfaceVariant"])

    svg, end = chips(28, H - 56, tags, MONO, 12.5, C["surfaceContainerHigh"], C["onSurfaceVariant"], h=28, pad=12)
    b += svg
    lw = BOLD.width(link, 14)
    assert end + 16 < W - 28 - 22 - lw, f"{name}: link collides with tags"
    b += text(W - 28 - 22, H - 37, link, BOLD, 14, C["primary"], "end")
    b += icon("arrow_outward", W - 28 - 18, H - 51, 18, C["primary"])
    return document(W, H, b, [SANS, BOLD, MONO])


def stack():
    groups = [
        ("sports_esports", "games", ["unity", "c#"]),
        ("public", "web", ["html", "css", "javascript", "typescript"]),
        ("terminal", "backend", ["python", "sql"]),
        ("smartphone", "mobile", ["react native", "expo"]),
    ]
    W, H = 1000, 200
    b = f'<rect width="{W}" height="{H}" rx="28" fill="{C["surfaceContainer"]}"/>'
    for i, (icon_name, label, items) in enumerate(groups):
        x = 32 + (i % 2) * 484
        y = 34 + (i // 2) * 82
        b += icon(icon_name, x, y - 2, 18, C["primary"])
        b += text(x + 26, y + 12, label, MONO, 13, C["outline"])
        svg, end = chips(x, y + 26, items, SANS, 15, C["surfaceContainerHighest"], C["onSurface"], h=32, pad=16)
        assert end < x + 460, f"{label} chips overflow"
        b += svg
    return document(W, H, b, [SANS, MONO])


def button(label, icon_name):
    size, h, pad = 15, 40, 20
    W = int(BOLD.width(label, size) + pad * 2 + 28) + 1
    b = f'<rect width="{W}" height="{h}" rx="{h / 2}" fill="{C["secondaryContainer"]}"/>'
    b += icon(icon_name, pad - 2, 11, 18, C["onSecondaryContainer"])
    b += text(pad + 24, h / 2 + size * 0.36, label, BOLD, size, C["onSecondaryContainer"])
    return document(W, h, b, [BOLD])


def main():
    ASSETS.mkdir(exist_ok=True)
    out = {
        "header.svg": header(),
        "nook.svg": project(
            "Nook", "study platform", "menu_book", C["primaryContainer"], C["onPrimaryContainer"],
            "in development",
            "The go-to study platform for students and hobbyists. Stay focused "
            "and engaged in whatever you're learning.",
            ["typescript", "web"], "nook-study.vercel.app"),
        "claven.svg": project(
            "Claven", "code editor", "code_blocks", C["tertiaryContainer"], C["onTertiaryContainer"],
            "early days",
            "Building a code editor from scratch. No roadmap yet, just a repo and a lot of curiosity.",
            ["typescript", "editor"], "view repo"),
        "stack.svg": stack(),
        "linkedin.svg": button("linkedin", "arrow_outward"),
        "itch.svg": button("itch.io", "sports_esports"),
    }
    for name, svg in out.items():
        (ASSETS / name).write_text(svg)
        print(f"{name:14} {len(svg) / 1024:6.1f} KiB")


if __name__ == "__main__":
    main()
