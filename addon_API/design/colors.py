"""
Цветовая математика для дизайна (без Qt - можно вызывать откуда угодно).

    from addon_API.design import colors as C
    C.lighten("#007acc", 10)      -> '#1a9cff'
    C.alpha("#007acc", 0.3)       -> 'rgba(0,122,204,0.30)'
    C.gradient(["#ff2d95", "#7a2dff"], angle=45)   -> 'qlineargradient(...)'
    C.palette_from_accent("#ff7a18", mode="dark")  -> {'bg': ..., 'accent': ...}

Цвет везде - строка: '#rgb', '#rrggbb', '#rrggbbaa', 'rgb(r,g,b)', 'rgba(r,g,b,a)'.
"""

import re
import math
import random
import colorsys

_RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)", re.I)
_NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000",
          "blue": "#0000ff", "yellow": "#ffff00", "transparent": "#00000000"}


# ------------------------------------------------------------------ #
# Разбор и вывод
# ------------------------------------------------------------------ #
def parse(color):
    """-> (r, g, b, a), r/g/b: 0..255, a: 0..1"""
    c = color.strip()
    c = _NAMED.get(c.lower(), c)
    m = _RGBA_RE.match(c)
    if m:
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), a
    c = c.lstrip("#")
    if len(c) in (3, 4):
        c = "".join(ch * 2 for ch in c)
    if len(c) == 6:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 1.0
    if len(c) == 8:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16) / 255
    raise ValueError(f"Не могу разобрать цвет: {color!r}")


def to_hex(r, g, b):
    clamp = lambda v: max(0, min(255, round(v)))
    return "#%02x%02x%02x" % (clamp(r), clamp(g), clamp(b))


def is_color(value):
    try:
        parse(value)
        return True
    except Exception:
        return False


def hex_of(color):
    r, g, b, _ = parse(color)
    return to_hex(r, g, b)


def alpha(color, a):
    """Цвет с прозрачностью a (0..1) -> 'rgba(r,g,b,a)' (для QSS)."""
    r, g, b, _ = parse(color)
    return "rgba(%d,%d,%d,%.2f)" % (r, g, b, max(0.0, min(1.0, a)))


# ------------------------------------------------------------------ #
# HLS-операции
# ------------------------------------------------------------------ #
def _hls(color):
    r, g, b, _ = parse(color)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def _from_hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0, min(1, l)), max(0, min(1, s)))
    return to_hex(r * 255, g * 255, b * 255)


def lighten(color, percent):
    h, l, s = _hls(color)
    return _from_hls(h, l + percent / 100, s)


def darken(color, percent):
    return lighten(color, -percent)


def saturate(color, percent):
    h, l, s = _hls(color)
    return _from_hls(h, l, s + percent / 100)


def desaturate(color, percent):
    return saturate(color, -percent)


def hue_shift(color, degrees):
    h, l, s = _hls(color)
    return _from_hls(h + degrees / 360, l, s)


def set_lightness(color, percent):
    h, _, s = _hls(color)
    return _from_hls(h, percent / 100, s)


def invert(color):
    r, g, b, _ = parse(color)
    return to_hex(255 - r, 255 - g, 255 - b)


def grayscale(color):
    r, g, b, _ = parse(color)
    v = 0.299 * r + 0.587 * g + 0.114 * b
    return to_hex(v, v, v)


def mix(c1, c2, t=0.5):
    """Смешать два цвета: t=0 -> c1, t=1 -> c2."""
    a, b = parse(c1), parse(c2)
    return to_hex(*(a[i] + (b[i] - a[i]) * t for i in range(3)))


# ------------------------------------------------------------------ #
# Контраст
# ------------------------------------------------------------------ #
def luminance(color):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b, _ = parse(color)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def is_dark(color):
    return luminance(color) < 0.4


def contrast_ratio(c1, c2):
    l1, l2 = sorted((luminance(c1), luminance(c2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def contrast_text(background, light="#ffffff", dark="#111111"):
    """Читаемый цвет текста для данного фона."""
    return light if contrast_ratio(background, light) >= contrast_ratio(background, dark) else dark


# ------------------------------------------------------------------ #
# Гармонии
# ------------------------------------------------------------------ #
def complementary(color):
    return hue_shift(color, 180)


def analogous(color, spread=30):
    return [hue_shift(color, -spread), color, hue_shift(color, spread)]


def triadic(color):
    return [color, hue_shift(color, 120), hue_shift(color, 240)]


def tetradic(color):
    return [color, hue_shift(color, 90), hue_shift(color, 180), hue_shift(color, 270)]


def shades(color, steps=5, spread=40):
    """Ряд оттенков от тёмного к светлому вокруг color."""
    h, l, s = _hls(color)
    out = []
    for i in range(steps):
        k = i / max(1, steps - 1)
        out.append(_from_hls(h, max(0.04, min(0.96, l - spread / 200 + k * spread / 100)), s))
    return out


def rainbow(t, saturation=0.85, lightness=0.55):
    """Цвет радуги, t: 0..1 (для анимаций)."""
    return _from_hls(t % 1.0, lightness, saturation)


# ------------------------------------------------------------------ #
# Градиенты для QSS
# ------------------------------------------------------------------ #
def gradient(stops, angle=90):
    """Линейный градиент QSS. stops: ["#a", "#b"] или [(0, "#a"), (1, "#b")].
    angle: 0 - слева направо, 90 - сверху вниз, 45 - по диагонали."""
    if stops and not isinstance(stops[0], (tuple, list)):
        n = max(1, len(stops) - 1)
        stops = [(i / n, c) for i, c in enumerate(stops)]
    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    x1, y1, x2, y2 = 0.5 - dx / 2, 0.5 - dy / 2, 0.5 + dx / 2, 0.5 + dy / 2
    parts = ", ".join("stop:%.3f %s" % (p, c) for p, c in stops)
    return "qlineargradient(x1:%.3f, y1:%.3f, x2:%.3f, y2:%.3f, %s)" % (x1, y1, x2, y2, parts)


def radial_gradient(stops, cx=0.5, cy=0.5, radius=0.7):
    if stops and not isinstance(stops[0], (tuple, list)):
        n = max(1, len(stops) - 1)
        stops = [(i / n, c) for i, c in enumerate(stops)]
    parts = ", ".join("stop:%.3f %s" % (p, c) for p, c in stops)
    return "qradialgradient(cx:%.2f, cy:%.2f, radius:%.2f, fx:%.2f, fy:%.2f, %s)" % (
        cx, cy, radius, cx, cy, parts)


# ------------------------------------------------------------------ #
# Палитры целиком
# ------------------------------------------------------------------ #
def palette_from_accent(accent, mode="dark", tint=0.12):
    """Строит полную палитру лаунчера (все роли TOKENS) из ОДНОГО акцентного цвета.
    mode: "dark" | "light";  tint: насколько фон подкрашен акцентом (0..0.4)."""
    h, _, s = _hls(accent)
    s_bg = max(0.0, min(1.0, s * tint * 2.5))
    if mode == "light":
        L = dict(bg=0.95, surface=1.0, surface_alt=0.92, surface_hover=0.96, border=0.80)
        text, muted = "#1b1f24", "#6a7380"
    else:
        L = dict(bg=0.04, surface=0.10, surface_alt=0.07, surface_hover=0.14, border=0.22)
        text, muted = "#f0f0f0", "#888888"
    p = {k: _from_hls(h, v, s_bg) for k, v in L.items()}
    p.update(text=text, text_muted=muted, accent=hex_of(accent),
             accent_dark=darken(accent, 10), accent_hover=lighten(accent, 8),
             editor_bg=_from_hls(h, L["surface_alt"], s_bg),
             editor_accent=darken(accent, 4))
    return p


def palette_from_hue(hue, mode="dark", saturation=0.8):
    """Палитра из оттенка 0..360."""
    return palette_from_accent(_from_hls(hue / 360, 0.5, saturation), mode)


def random_palette(seed=None, mode="dark"):
    rnd = random.Random(seed)
    return palette_from_hue(rnd.uniform(0, 360), mode, rnd.uniform(0.55, 0.95))
