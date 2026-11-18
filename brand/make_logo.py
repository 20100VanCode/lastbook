#!/usr/bin/env python3
"""Generate the RELIQUE mark: a halftone disc, a crosshair, an open book and a node dot.
Vector (SVG) and raster (PNG, via Pillow) from the same geometry, so they always agree.
VAN CODE-derived: monochrome, dithered, no smooth gradient, no drop shadow."""
from pathlib import Path
import math

INK = (17, 17, 17)
PAPER = (242, 239, 231)
ACCENT = (138, 43, 31)
SIZE = 512
CX, CY = 256.0, 246.0
R = 208.0
CELL = 17.0
N = 28


def cells():
    """Yield (x, y, t) for each grid cell whose centre is inside the disc.
    t is 0 at the rim, 1 at the centre: the halftone tone."""
    half = N * CELL / 2
    for j in range(N):
        for i in range(N):
            x = CX - half + (i + 0.5) * CELL
            y = CY - half + (j + 0.5) * CELL
            d = math.hypot(x - CX, y - CY)
            if d > R:
                continue
            yield x, y, max(0.0, 1.0 - (d / R) ** 2)


def book_path():
    """Open book: two paper quadrilaterals meeting at the fold."""
    top, bot, mid = CY - 22, CY + 58, CY + 18
    left, right, fold = CX - 96, CX + 96, CX
    return (f"M {left} {top} L {fold} {mid} L {fold} {bot - 14} L {left} {bot} Z "
            f"M {right} {top} L {fold} {mid} L {fold} {bot - 14} L {right} {bot} Z")


def svg():
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" role="img" aria-label="RELIQUE">',
         f'<rect width="{SIZE}" height="{SIZE}" rx="26" fill="#{INK[0]:02x}{INK[1]:02x}{INK[2]:02x}"/>']
    # crosshair (cartography) in accent, behind the halftone
    p.append(f'<g stroke="#{ACCENT[0]:02x}{ACCENT[1]:02x}{ACCENT[2]:02x}" stroke-width="2" opacity="0.85">'
             f'<path d="M {CX} {CY - R - 18} V {CY + R + 18}"/>'
             f'<path d="M {CX - R - 18} {CY} H {CX + R + 18}"/></g>')
    # halftone disc: dot radius grows towards the centre
    for x, y, t in cells():
        r = CELL * 0.46 * (0.10 + 0.90 * t)
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#{PAPER[0]:02x}{PAPER[1]:02x}{PAPER[2]:02x}" opacity="0.92"/>')
    # open book
    p.append(f'<path d="{book_path()}" fill="#{PAPER[0]:02x}{PAPER[1]:02x}{PAPER[2]:02x}"/>')
    p.append(f'<path d="M {CX} {CY + 4} V {CY + 44}" stroke="#{INK[0]:02x}{INK[1]:02x}{INK[2]:02x}" stroke-width="4"/>')
    # node dot
    p.append(f'<circle cx="{CX}" cy="{CY - R - 34}" r="11" fill="#{ACCENT[0]:02x}{ACCENT[1]:02x}{ACCENT[2]:02x}"/>')
    p.append('</svg>')
    return '\n'.join(p)


def png(size, out):
    from PIL import Image, ImageDraw
    s = size / SIZE
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(26 * s), fill=INK + (255,))
    def hx(c): return f'#{c[0]:02x}{c[1]:02x}{c[2]:02x}'
    d.line([(CX * s, (CY - R - 18) * s), (CX * s, (CY + R + 18) * s)], fill=ACCENT, width=max(1, int(2 * s)))
    d.line([((CX - R - 18) * s, CY * s), ((CX + R + 18) * s, CY * s)], fill=ACCENT, width=max(1, int(2 * s)))
    for x, y, t in cells():
        r = CELL * 0.46 * (0.10 + 0.90 * t) * s
        d.ellipse([x * s - r, y * s - r, x * s + r, y * s + r], fill=PAPER + (235,))
    top, bot, mid = CY - 22, CY + 58, CY + 18
    left, right, fold = CX - 96, CX + 96, CX
    d.polygon([(left * s, top * s), (fold * s, mid * s), (fold * s, (bot - 14) * s), (left * s, bot * s)], fill=PAPER + (255,))
    d.polygon([(right * s, top * s), (fold * s, mid * s), (fold * s, (bot - 14) * s), (right * s, bot * s)], fill=PAPER + (255,))
    d.line([(fold * s, (CY + 4) * s), (fold * s, (CY + 44) * s)], fill=INK, width=max(1, int(4 * s)))
    r = 11 * s
    d.ellipse([(CX * s - r), (CY - R - 34) * s - r, (CX * s + r), (CY - R - 34) * s + r], fill=ACCENT + (255,))
    im.save(out)


def favicon():
    """Simplified mark for the browser tab: ink square, paper book, accent dot."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="RELIQUE">'
            '<rect width="64" height="64" rx="10" fill="#111111"/>'
            '<path d="M10 22 L26 30 L26 48 L10 42 Z M54 22 L38 30 L38 48 L54 42 Z" fill="#f2efe7"/>'
            '<circle cx="32" cy="12" r="4" fill="#8a2b1f"/></svg>')


if __name__ == '__main__':
    here = Path(__file__).resolve().parent
    root = here.parent
    (root / 'web' / 'icon.svg').write_text(svg(), encoding='utf-8')
    (root / 'web' / 'favicon.svg').write_text(favicon(), encoding='utf-8')
    png(192, root / 'web' / 'icon-192.png')
    png(512, root / 'web' / 'icon-512.png')
    (here / 'relique-mark.svg').write_text(svg(), encoding='utf-8')
    print('icon.svg, favicon.svg, icon-192.png, icon-512.png, brand/relique-mark.svg')
