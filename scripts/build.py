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

laptop-terminal.svg is foot as it opens on the main laptop: Caelestia's greeting and a
fastfetch box of the laptop's specs, in the terminal colours Caelestia writes into foot and the
locally installed JetBrains Mono Nerd Font that foot uses.

hp-terminal.svg is the old HP laptop's fastfetch in its Ghostty window. Its colours are
read off a photo of that screen, so it stays fixed, and its fish logo is the braille in
scripts/hp-fish.txt, recovered dot by dot from the same photo.
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

FISH = ROOT / "scripts" / "hp-fish.txt"

RUBIK_URL = "https://github.com/google/fonts/raw/main/ofl/rubik/Rubik%5Bwght%5D.ttf"
MONO_URL = "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf"
NERD_FONT = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-{}.ttf"
NOOK_ICON_URL = "https://nook-study.com/branding/icon-512.png"
ICON_URL = (
    "https://raw.githubusercontent.com/google/material-design-icons/master/"
    "symbols/web/{0}/materialsymbolsrounded/{0}_24px.svg"
)
CHARS = "".join(chr(c) for c in range(32, 127)) + "·—’↗"

# Primary of the scheme the README was first built with, used if scheme.json is missing.
FALLBACK_SEED = "f9b7a6"


def load_scheme():
    try:
        return json.loads(SCHEME.read_text())["colours"]
    except (OSError, KeyError, ValueError):
        return {}


def load_seed():
    return load_scheme().get("primary", FALLBACK_SEED)


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

    def __init__(self, family, ttfont, chars=CHARS):
        self.family = family
        opts = Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        sub = Subsetter(opts)
        sub.populate(text=chars)
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


def mono(weight):
    var = TTFont(fetch(MONO_URL, CACHE / "JetBrainsMono.ttf"))
    return Font(f"mono{weight}", instantiateVariableFont(var, {"wght": weight}), CHARS + "°")


SANS = rubik(400)
BOLD = rubik(600)
MONO = mono(400)
MONO_BOLD = mono(700)

# icon, key, value per row; the icons are Nerd Font glyphs, and the first two columns' worth
# reuse the ones in Caelestia's fastfetch config
LAPTOP_SPECS = (
    [("\U000f0322", "laptop", "HP Laptop 15 (fc0xxx)"),
     ("", "cpu", "AMD Ryzen 7 7730U (8C/16T)"),
     ("\U000f08ae", "gpu", "AMD Radeon (integrated)"),
     ("", "mem", "10.31 GiB / 14.96 GiB"),
     ("\U000f02ca", "disk", "512 GB Samsung NVMe, btrfs"),
     ("\U000f0379", "screen", '15.6" 1366x768'),
     ("\U000f0379", "monitor", 'Dell P2419HC 24" 1080p'),
     ("", "uptime", "1 day, 19 hours")],
    [("\U000f0ec0", "distro", "CachyOS"),
     ("", "kernel", "7.2.9-1-cachyos"),
     ("", "wm", "Hyprland 0.56 (Wayland)"),
     ("", "de", "Caelestia shell"),
     ("", "term", "foot 1.28"),
     ("\U000f023a", "shell", "fish 4.9"),
     ("", "editor", "Neovim 0.12"),
     ("", "pkgs", "1310 (pacman)")],
)
# colour per row, in the same order Caelestia's fastfetch config colours its rows
ROW_COLOURS = ["primary", None, "primary", "secondary", None, "primary", None, "tertiary"]
GREETING = r"""     ______           __          __  _
    / ____/___ ____  / /__  _____/ /_(_)___ _
   / /   / __ `/ _ \/ / _ \/ ___/ __/ / __ `/
  / /___/ /_/ /  __/ /  __(__  ) /_/ / /_/ /
  \____/\__,_/\___/_/\___/____/\__/_/\__,_/""".splitlines()
NERD_CHARS = CHARS + "╭╮╰╯─│◎⌂" + "".join(icon for box in LAPTOP_SPECS for icon, _, _ in box)
NERD = Font("nerd400", TTFont(NERD_FONT.format("Regular")), NERD_CHARS)
NERD_BOLD = Font("nerd700", TTFont(NERD_FONT.format("Bold")), NERD_CHARS)
# Caelestia's terminal colours as of the last build, used if scheme.json is missing
FALLBACK_TERM = {"primary": "d1bfeb", "secondary": "cdc2db", "tertiary": "ffd8ed", "surface": "0f0d12",
                 "onSurface": "ebe3ef", "term4": "a4a6d8", "term7": "e8d3de", "term11": "fff0f6"}


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


HP = {
    "top": "#0a1638", "bottom": "#1a49b8", "bar": "#09122e", "chrome": "#b8c4de",
    "fg": "#e9eef8", "fish": "#7bd6ec", "green": "#72e08f", "os": "#7fe6c6", "hw": "#8fd8f6",
    "pink": "#ff7f9f", "pill": "#a7c7ff", "pill2": "#d8e5ff", "ink": "#0a1638",
}
# fastfetch's colour row, as that terminal's palette draws it
HP_PALETTE = ["#e9eef8", "#e9eef8", "#e9eef8", "#7bd6ec", "#e9eef8", "#e9eef8", "#ff8fa8"]
# braille bit i raises the dot at (column, row) BRAILLE[i] of its 2x4 cell
BRAILLE = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]


def line(x, y, parts, size, cw=None):
    """One line of terminal text, each (text, font, colour) part in its own tspan. Given a cell
    width, each part is pinned to its column, so wide Nerd Font icons can't push the rest along."""
    spans, col = "", 0
    for s, f, c in parts:
        at = f' x="{x + col * cw:.1f}"' if cw else ""
        spans += f'<tspan{at} font-family="{f.family}" fill="{c}">{s.replace("&", "&amp;").replace("<", "&lt;")}</tspan>'
        col += len(s)
    return f'<text x="{x}" y="{y}" font-size="{size}" xml:space="preserve">{spans}</text>'


def fish(x, y, pitch, fill):
    """The fastfetch logo, one round dot per raised braille point."""
    d = "".join(f"M{2 * col + dx} {4 * row + dy}h0"
                for row, text_line in enumerate(FISH.read_text().splitlines())
                for col, ch in enumerate(text_line)
                for i, (dx, dy) in enumerate(BRAILLE) if (ord(ch) - 0x2800) >> i & 1)
    return (f'<path transform="translate({x} {y}) scale({pitch})" d="{d}" fill="none" stroke="{fill}" '
            f'stroke-width="0.5" stroke-linecap="round"/>')


def prompt(x, y, C):
    """The HP's bash prompt: user and path segments, two chevrons, then the clock."""
    user, path, clock = "pheonix1", "~", "23:12"
    w1 = 30 + MONO.width(user, 13) + 8
    w2 = MONO.width(path, 13) + 26
    x2, x3 = x + w1, x + w1 + w2
    b = f'<path d="M{x2} {y}H{x3}l10 12l-10 12H{x2}Z" fill="{C["pill2"]}"/>'
    b += f'<path d="M{x + 12} {y}H{x2}l10 12l-10 12H{x + 12}a12 12 0 0 1 0-24Z" fill="{C["pill"]}"/>'
    b += f'<circle cx="{x + 15}" cy="{y + 12}" r="6.5" fill="{C["ink"]}"/><circle cx="{x + 15}" cy="{y + 12}" r="2.5" fill="{C["pill"]}"/>'
    b += text(x + 28, y + 17, user, MONO, 13, C["ink"])
    b += text(x2 + 18, y + 17, path, MONO, 13, C["ink"])
    cx = x3 + 16
    for dx, colour in (0, C["pink"]), (7, C["green"]):
        b += (f'<path d="M{cx + dx} {y + 4}l7 8l-7 8" fill="none" stroke="{colour}" stroke-width="3" '
              f'stroke-linejoin="round"/>')
    x4 = cx + 18
    w4 = 34 + MONO.width(clock, 13)
    b += f'<path d="M{x4} {y}H{x4 + w4 - 12}a12 12 0 0 1 0 24H{x4}l10-12Z" fill="{C["pill"]}"/>'
    b += (f'<circle cx="{x4 + 20}" cy="{y + 12}" r="6" fill="none" stroke="{C["ink"]}" stroke-width="1.6"/>'
          f'<path d="M{x4 + 20} {y + 8.5}V{y + 12}h3" fill="none" stroke="{C["ink"]}" stroke-width="1.6" stroke-linecap="round"/>')
    b += text(x4 + 30, y + 17, clock, MONO, 13, C["ink"])
    return b, x4 + w4


def chrome(W, bar, C):
    """Ghostty's GTK header bar: new-tab button, title, then tab overview, menu and window buttons."""
    s = f'stroke="{C["chrome"]}" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    m = bar / 2
    b = f'<rect width="{W}" height="{bar}" fill="{C["bar"]}"/><path d="M0 {bar}.5H{W}" stroke="#ffffff" stroke-opacity="0.08"/>'
    b += f'<rect x="16" y="{m - 7}" width="16" height="14" rx="3" {s}/><path d="M24 {m - 3}v6M21 {m}h6M40 {m - 2}l3 3l3-3" {s}/>'
    b += text(W / 2, m + 5, "fastfetch", MONO_BOLD, 13, C["fg"], "middle")
    r = W - 22
    b += f'<path d="M{r - 5} {m - 5}l10 10M{r + 5} {m - 5}l-10 10" {s}/>'
    b += f'<rect x="{r - 41}" y="{m - 5}" width="10" height="10" rx="1.5" {s}/>'
    b += f'<path d="M{r - 73} {m + 5}h10" {s}/>'
    b += "".join(f'<circle cx="{r - 102}" cy="{m + dy}" r="1.4" fill="{C["chrome"]}"/>' for dy in (-5, 0, 5))
    b += "".join(f'<rect x="{r - 140 + dx}" y="{m - 6 + dy}" width="5" height="5" rx="1" {s}/>'
                 for dx in (0, 7) for dy in (0, 7))
    return b


CURSOR_CSS = ("@keyframes blink{50%{opacity:0}}.cursor{animation:blink 1.1s steps(1) infinite}"
              "@media (prefers-reduced-motion:reduce){.cursor{animation:none}}")


def fastfetch_box(rows, C, width=26):
    """Caelestia's fastfetch layout: a rounded box, icon and key on the left, value right-aligned."""
    edge = "─" * (width + 14)
    lines = [[("╭" + edge + "╮", NERD_BOLD, C["term7"])]]
    for (icon, key, value), colour in zip(rows, ROW_COLOURS):
        c = C[colour] if colour else None
        lines.append([("│ ", NERD_BOLD, C["term7"]), (icon, NERD_BOLD, c or C["term7"]),
                      ("  " + key.ljust(7), NERD_BOLD, C["term7"]),
                      ("  " + value.rjust(width), NERD, c or C["onSurface"]), (" │", NERD, C["term7"])])
    lines.append([("╰" + edge + "╯", NERD_BOLD, C["term7"])])
    return lines


def foot_terminal():
    """foot on the main laptop as it opens: Caelestia's greeting, fastfetch, then the starship prompt."""
    C = {k: "#" + v for k, v in {**FALLBACK_TERM, **load_scheme()}.items()}
    size, lh, pad = 14, 19, 25
    cw = NERD.width("m", size)
    left, right = (fastfetch_box(rows, C) for rows in LAPTOP_SPECS)
    lines = [[(s, NERD, C["primary"])] for s in GREETING] + [[]]
    lines += [[("     ", NERD, C["onSurface"])] + a + [("   ", NERD, C["onSurface"])] + b for a, b in zip(left, right)]
    lines += [[]]
    cols = max(sum(len(s) for s, _, _ in parts) for parts in lines)
    W = round(2 * pad + cols * cw)
    H = 2 * pad + (len(lines) + 1) * lh

    b = (f'<defs><radialGradient id="foot-glow" cx="0.85" cy="0" r="0.9"><stop offset="0" stop-color="{C["primary"]}" '
         f'stop-opacity="0.16"/><stop offset="1" stop-color="{C["primary"]}" stop-opacity="0"/></radialGradient>'
         f'<radialGradient id="foot-glow2" cx="0.05" cy="1" r="0.7"><stop offset="0" stop-color="{C["tertiary"]}" '
         f'stop-opacity="0.08"/><stop offset="1" stop-color="{C["tertiary"]}" stop-opacity="0"/></radialGradient></defs>'
         f'<rect width="{W}" height="{H}" rx="15" fill="{C["surface"]}"/>'
         f'<rect width="{W}" height="{H}" rx="15" fill="url(#foot-glow)"/><rect width="{W}" height="{H}" rx="15" fill="url(#foot-glow2)"/>')
    for i, parts in enumerate(lines):
        if parts:
            b += line(pad, pad + 14 + i * lh, parts, size, cw)
    y = pad + 14 + len(lines) * lh
    b += (f'<text x="{pad}" y="{y}" font-family="{NERD_BOLD.family}" font-size="{size}" font-style="italic" '
          f'fill="{C["term11"]}">◎</text>')
    b += f'<rect class="cursor" x="{pad + 2 * cw:.1f}" y="{y - 13}" width="1.5" height="17" fill="{C["secondary"]}"/>'
    b += (f'<text x="{W - pad}" y="{y}" font-family="{NERD.family}" font-size="{size}" font-style="italic" '
          f'text-anchor="end" xml:space="preserve"><tspan fill="{C["term4"]}">⌂</tspan>'
          f'<tspan fill="{C["term7"]}" fill-opacity="0.6"> 12:43</tspan></text>')
    b += (f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14.5" fill="none" stroke="{C["primary"]}" '
          f'stroke-opacity="0.9"/>')
    return document(W, H, b, [NERD, NERD_BOLD], CURSOR_CSS)


def hp_terminal():
    """The old HP's fastfetch, as it sits in its Ghostty window."""
    C = HP
    size, lh, bar, pitch = 14, 20, 40, 3.6
    cw = MONO.width("m", size)

    def row(key, colour, *value):
        parts = [(key.ljust(10), MONO_BOLD, colour)]
        return parts + [(v, MONO, C["fg"]) if isinstance(v, str) else v for v in value]

    info = [
        [("pheonix1", MONO_BOLD, C["green"]), ("@", MONO, C["fg"]), ("pheonix1-HP", MONO_BOLD, C["green"])],
        [],
        row("OS", C["os"], "Xubuntu 24.04.4 LTS x86_64"),
        row("Kernel", C["os"], "Linux 6.17.0-35-generic"),
        row("Shell", C["os"], "bash 5.2.21"),
        row("DE", C["os"], "Xfce4 4.18"),
        row("Packages", C["os"], "1815 (dpkg), 14 (snap)"),
        [],
        row("CPU", C["hw"], "Intel Core i5-4300M (4) @ 3.30 GHz - ", ("57.0°C", MONO, C["green"])),
        row("GPU", C["hw"], "Intel HD Graphics 4600 [Integrated]"),
        row("RAM", C["hw"], "3.36 GiB / 7.65 GiB (", ("44%", MONO, C["green"]), ")"),
        row("Disk", C["hw"], "21.95 GiB / 232.64 GiB (", ("9%", MONO, C["green"]), ") - ext4"),
        [],
        row("Uptime", C["pink"], "128 days(!), 8 hours, 39 mins"),
        row("Battery", C["fg"], "60% [Discharging]"),
        [],
    ]
    rows = FISH.read_text().splitlines()
    fw, fh = (2 * max(map(len, rows)) - 1) * pitch, (4 * len(rows) - 1) * pitch
    ix = round(32 + fw + 44)
    W = round(ix + max(sum(len(s) for s, _, _ in parts) for parts in info) * cw + 36)
    top = bar + 18
    body_top = top + 24 + 26
    body_h = (len(info) + 1) * lh
    H = body_top + body_h + 20 + 24 + 22

    b = (f'<defs><linearGradient id="hp-bg" x1="0" y1="0" x2="0.4" y2="1"><stop offset="0" stop-color="{C["top"]}"/>'
         f'<stop offset="1" stop-color="{C["bottom"]}"/></linearGradient>'
         f'<clipPath id="hp-win"><rect width="{W}" height="{H}" rx="12"/></clipPath></defs>'
         f'<g clip-path="url(#hp-win)"><rect width="{W}" height="{H}" fill="url(#hp-bg)"/>{chrome(W, bar, C)}')
    p, end = prompt(24, top, C)
    b += p + text(end + 12, top + 17, "fastfetch", MONO, size, C["fg"])
    b += fish(32, round(body_top + (body_h - fh) / 2, 1), pitch, C["fish"])
    for i, parts in enumerate(info):
        if parts:
            b += line(ix, body_top + 14 + i * lh, parts, size)
    dots_y = body_top + 9 + len(info) * lh
    b += "".join(f'<circle cx="{ix + 6 + i * 22}" cy="{dots_y}" r="6" fill="{c}"/>' for i, c in enumerate(HP_PALETTE))
    y = body_top + body_h + 20
    p, end = prompt(24, y, C)
    b += p + f'<rect class="cursor" x="{end + 12}" y="{y + 3}" width="{cw:.1f}" height="18" fill="{C["fg"]}"/>'
    b += f'</g><rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="11.5" fill="none" stroke="#ffffff" stroke-opacity="0.1"/>'
    return document(W, H, b, [MONO, MONO_BOLD], CURSOR_CSS)


def main():
    ASSETS.mkdir(exist_ok=True)
    out = {"laptop-terminal.svg": foot_terminal(), "hp-terminal.svg": hp_terminal()}
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
