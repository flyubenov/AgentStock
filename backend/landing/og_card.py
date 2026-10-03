"""The /t/{TICKER} share card (spec 2026-10-03 §5): a 1200x630 teal PNG with the
ticker and the three questions, no numbers. Drawn on first request and kept in a
small LRU. Callers must only pass tickers that are on the SEC list (routers/og.py)."""
from __future__ import annotations
import io
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_GROTESK = _FONTS / "SpaceGrotesk[wght].ttf"
_INTER = _FONTS / "Inter[opsz,wght].ttf"

# Kept equal to frontend/src/landing/components/mark.ts MARK (test_og_card checks).
CARD_COLOURS = {
    "plateTop": "#17696f", "plateBot": "#0a3a3e", "rim": "#8fc4c5",
    "q": "#66fff7", "mo": "#3d8bff", "fv": "#fae842", "rr": "#440ab8",
}
_SMALL = "#cfe6e4"
_LINE = "Quality · Moat · Fair Value · Reward/Risk, scored from fundamentals"
_QUESTIONS = [[("q", "Quality business?"), ("mo", "Durable moat?")], [("fv", "Fair price?")]]
_LEFT, _RIGHT = 78, W - 72

_cache: OrderedDict[str, bytes] = OrderedDict()
_MAX = 256


def _font(path: Path, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    axes = f.get_variation_axes()
    f.set_variation_by_axes([weight if a["name"] in (b"Weight", "Weight") else
                             max(a["minimum"], min(a["maximum"], size)) for a in axes])
    return f


def _rgb(hex_: str) -> tuple[int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))


def _ticker_font(ticker: str) -> ImageFont.FreeTypeFont:
    size = 156
    while size > 60:
        f = _font(_GROTESK, size, 700)
        if f.getlength(ticker) <= 0.6 * W:
            return f
        size -= 6
    return _font(_GROTESK, size, 700)


def ticker_width(ticker: str) -> float:
    return _ticker_font(ticker).getlength(ticker)


def _gradient() -> Image.Image:
    top, bot = _rgb(CARD_COLOURS["plateTop"]), _rgb(CARD_COLOURS["plateBot"])
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        k = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bot)))
    return img


def _mark(img: Image.Image, x: int, y: int, s: int) -> None:
    """The keyhole mark: rounded plate and four quadrants inside the keyhole, drawn
    with a mask (mark.ts KEYHOLE: head circle r=15 at (50,36), slot to y=80)."""
    k = s / 100
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x + 4 * k, y + 4 * k, x + 96 * k, y + 96 * k], radius=22 * k,
                        fill=_rgb(CARD_COLOURS["plateTop"]), outline=_rgb(CARD_COLOURS["rim"]), width=2)
    mask = Image.new("L", (s, s), 0)
    m = ImageDraw.Draw(mask)
    m.ellipse([35 * k, 21 * k, 65 * k, 51 * k], fill=255)
    m.polygon([(43.1 * k, 51.3 * k), (56.9 * k, 51.3 * k), (62 * k, 80 * k), (38 * k, 80 * k)], fill=255)
    quad = Image.new("RGB", (s, s))
    q = ImageDraw.Draw(quad)
    q.rectangle([0, 0, s / 2, 53 * k], fill=_rgb(CARD_COLOURS["q"]))
    q.rectangle([s / 2, 0, s, 53 * k], fill=_rgb(CARD_COLOURS["mo"]))
    q.rectangle([0, 53 * k, s / 2, s], fill=_rgb(CARD_COLOURS["fv"]))
    q.rectangle([s / 2, 53 * k, s, s], fill=_rgb(CARD_COLOURS["rr"]))
    img.paste(quad, (x, y), mask)


def _draw(ticker: str) -> bytes:
    img = _gradient()
    d = ImageDraw.Draw(img)
    _mark(img, _LEFT, 60, 64)
    d.text((_LEFT + 82, 92), "Intrinsica", font=_font(_GROTESK, 38, 700), fill="white", anchor="lm")
    d.text((_LEFT - 6, 150), ticker, font=_ticker_font(ticker), fill="white")
    qf = _font(_GROTESK, 54, 600)
    y = 330
    for line in _QUESTIONS:
        x = _LEFT
        for key, text in line:
            d.ellipse([x, y + 22, x + 18, y + 40], fill=_rgb(CARD_COLOURS[key]))
            x += 30
            d.text((x, y), text, font=qf, fill="white")
            x += qf.getlength(text) + 34
        y += 68
    # 18% white over the gradient: blended by hand, since an RGB image ignores alpha.
    base = img.getpixel((_LEFT, 494))
    d.line([(_LEFT, 494), (_RIGHT, 494)], fill=tuple(round(c + (255 - c) * 0.18) for c in base), width=1)
    small = _font(_INTER, 25, 400)
    d.text((_LEFT, 536), _LINE, font=small, fill=_SMALL, anchor="lm")
    d.text((_RIGHT, 536), "intrinsica.io", font=_font(_INTER, 25, 700), fill="white", anchor="rm")
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def render_card(ticker: str) -> bytes:
    if ticker in _cache:
        _cache.move_to_end(ticker)
        return _cache[ticker]
    png = _draw(ticker)
    _cache[ticker] = png
    if len(_cache) > _MAX:
        _cache.popitem(last=False)
    return png
