"""Render the PNG app icons from the same geometry as src/icons/icon.svg (Pillow only).
Rounded corners for the 'any' icons; full-bleed squares for apple-touch-icon and maskable
(the OS applies its own mask). The glyph sits inside the 80% maskable safe zone."""
import sys, pathlib
from PIL import Image, ImageDraw
out = pathlib.Path(sys.argv[1])
S = 2048; u = S / 32
NAVY, CYAN = (13, 20, 36), (6, 182, 212)
SQUARES = [(8, 8, 1), (19, 8, .6), (13.5, 13.5, .8), (8, 19, .5), (19, 19, 1)]
def render(rounded):
    bg = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(bg)
    if rounded: d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(7 * u), fill=NAVY + (255,))
    else: d.rectangle([0, 0, S, S], fill=NAVY + (255,))
    for x, y, a in SQUARES:
        layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle([x * u, y * u, (x + 5) * u - 1, (y + 5) * u - 1], fill=CYAN + (int(255 * a),))
        bg = Image.alpha_composite(bg, layer)
    return bg
r, s = render(True), render(False).convert('RGB')
for name, im, size in [('icon-192.png', r, 192), ('icon-512.png', r, 512), ('icon-maskable-512.png', s, 512), ('apple-touch-icon.png', s, 180)]:
    im.resize((size, size), Image.LANCZOS).save(out / name, optimize=True)
print('icons written to', out)
