"""Pictures for the closing two-shot and the clearer guidance of CUT 6 (assets_v10).

usage: python3 tools/v10_prep.py SRC ASSETS_V4 ASSETS_V8 OUT
  SRC        official_turnaround.jpg (the official's turnaround sheet), citizen_turnaround.png (the citizen's)
  ASSETS_V4  v4_cz_34_neutral.png;  ASSETS_V8  v8_cz_34_talk.png
  writes
  OUT/v10_official_side.png CUT 7: the official, full figure, side view facing screen-left, toward the citizen (as drawn: his
                            bag strap stays on the same shoulder as in every other shot; the sheet's 3/4 view turns too little
                            to read as facing him), keyed off the sheet and upscaled 3x
  OUT/v10_cz_34_full.png    CUT 7: the citizen, full figure, 3/4 view, mirrored to face screen-right: the screen geography of
                            the whole consultation (he on the left, the official on the right)
  OUT/v10_cz_34_neutral.png, OUT/v10_cz_34_talk.png
                            CUT 6: his 3/4 face (v4 / v8) without the light halo the upscale left round the pupils, so his
                            eyes can close (the understanding nod, the relieved smile) without a pale ring
  OUT/v10_meta.json         size, feet, eyes [x, y, w, h] and the skin round the eyes (for the lids)

Keying and upscale are read from tools/v4_prep.py itself, so these pictures go through the same steps as the others.
"""
import ast, json, os, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC, V4, V8, OUT = sys.argv[1:5]
HERE = os.path.dirname(os.path.abspath(__file__))
ns = {"np": np, "Image": Image, "ImageDraw": ImageDraw, "ImageFilter": ImageFilter, "deque": deque,
      "INK": np.array([38, 33, 31], np.float32), "K": 3}
tree = ast.parse(open(os.path.join(HERE, "v4_prep.py"), encoding="utf-8").read())
funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("components", "key_cell", "upscale")]
exec(compile(ast.Module(body=funcs, type_ignores=[]), "v4_prep.py", "exec"), ns)
key_cell, upscale, components = ns["key_cell"], ns["upscale"], ns["components"]
os.makedirs(OUT, exist_ok=True)
meta = {}


def find_eyes(arr, head_frac=0.3):
    """The two pupils: dark, compact, upright blobs inside the head (the hair is one big dark mass and is skipped)."""
    a = arr.astype(int)
    ys, xs = np.nonzero(a[..., 3] > 128)
    top, bot = ys.min(), ys.max()
    y1 = int(top + head_frac * (bot - top))
    dark = (a[..., :3].sum(-1) < 240) & (a[..., 3] > 200)
    dark[y1:] = False
    found = []
    for c in components(dark, 60):
        h = c[:, 0].max() - c[:, 0].min() + 1; w = c[:, 1].max() - c[:, 1].min() + 1
        if 60 <= len(c) <= 4000 and 1.15 <= h / w <= 3.2 and len(c) > 0.5 * h * w:
            found.append((len(c), float(c[:, 1].mean()), float(c[:, 0].mean()), int(w), int(h)))
    found.sort(reverse=True)
    eyes = sorted(found[:2], key=lambda e: e[1])
    return [[round(x, 1), round(y, 1), w, h] for _, x, y, w, h in eyes]


def clean_eyes(arr, eyes):
    """Fill the light halo round each pupil with the skin round it (diffused inward); the pupil keeps a soft edge.
    Returns the picture and the median skin just outside the halos (the colour for a lid painted over the eye)."""
    im = arr.copy()
    skins = []
    for EX, EY, _, EH in eyes:
        r = int(EH * 0.9) + 12
        x0, y0 = max(0, int(EX - r)), max(0, int(EY - r))
        x1, y1 = min(im.shape[1], int(EX + r)), min(im.shape[0], int(EY + r))
        win = im[y0:y1, x0:x1].astype(np.float32)
        lum = win[..., :3].sum(-1)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        core = (lum < 330) & (((xx - EX) / (EX * 0 + 1)) ** 2 < 1e9) & ((yy - EY) ** 2 + (xx - EX) ** 2 < (EH * 0.75) ** 2)
        near = np.asarray(Image.fromarray((core * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(17))) > 0
        rim = np.asarray(Image.fromarray((near * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(7))) > 0
        ring = win[rim & ~near & (win[..., 3] > 250)][:, :3]
        skin = np.median(ring, axis=0)
        skins.append(skin)
        F = win[..., :3].copy()
        F[near] = skin
        for _ in range(600):
            avg = (np.roll(F, 1, 0) + np.roll(F, -1, 0) + np.roll(F, 1, 1) + np.roll(F, -1, 1)) / 4
            F[near] = avg[near]
        wgt = np.clip((620 - lum) / 470, 0, 1)
        wgt[~near] = 0
        wgt = wgt[..., None]
        pupil = np.where(core[..., None], win[..., :3], np.array([22, 16, 16], np.float32))
        im[y0:y1, x0:x1, :3] = np.clip(wgt * pupil + (1 - wgt) * F, 0, 255).astype(np.uint8)
    return im, [int(v) for v in np.median(np.array(skins), axis=0)]


def feet(arr):
    a = arr[..., 3] > 128
    ys, xs = np.nonzero(a)
    bot = ys.max()
    low = xs[ys > bot - 30]
    return [round(float((low.min() + low.max()) / 2), 1), int(bot)], [int(xs.min()), int(ys.min()), int(xs.max()), int(bot)]


def only_figure(arr):
    """Drop loose scraps the keying left (a bit of the sheet's floor line by the shoes): keep the figure's own pieces."""
    a = arr.copy()
    solid = a[..., 3] > 128
    parts = components(solid, 1)
    big = max(len(c) for c in parts)
    for c in parts:
        if len(c) < 0.02 * big:
            a[c[:, 0], c[:, 1], 3] = 0
    a[..., 3] = np.where(np.asarray(Image.fromarray(((a[..., 3] > 0) * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(5))) > 0, a[..., 3], 0)
    return a


def trim_floor(arr, band=150):
    """Below the shoes: bits of the sheet's ground line and shadow stay attached to the soles. In each column of the bottom
    band, clear everything under the lowest shoe (dark) pixel."""
    a = arr.copy()
    H = a.shape[0]
    ys, xs = np.nonzero(a[..., 3] > 128)
    bot = ys.max()
    y0 = max(0, bot - band)
    lum = a[..., :3].astype(int).sum(-1)
    for x in range(a.shape[1]):
        col = (lum[y0:bot + 1, x] < 450) & (a[y0:bot + 1, x, 3] > 200)
        hit = np.nonzero(col)[0]
        cut = y0 + (hit.max() + 3 if len(hit) else 0)
        a[cut:, x, 3] = 0
    return a


def card(arr):
    """The ID card on his chest: its white face under the teal band, [centre x, centre y, width, height, tilt°, band height].
    Searched for between the collar and the belt only (the light-blue tablet at his hip would pass the colour test too)."""
    a = arr.astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    ys, xs = np.nonzero(a[..., 3] > 128)
    top, bot = ys.min(), ys.max()
    chest = np.zeros(a.shape[:2], bool); chest[int(top + 0.33 * (bot - top)):int(top + 0.47 * (bot - top))] = True
    teal = (g > r + 45) & (b > r + 30) & (g > 110) & (a[..., 3] > 250) & chest
    tc = max(components(teal, 200), key=len)
    tx0, tx1, ty0, ty1 = tc[:, 1].min(), tc[:, 1].max(), tc[:, 0].min(), tc[:, 0].max()
    white = (r > 228) & (g > 228) & (b > 228) & (a[..., 3] > 250)
    region = np.zeros_like(white); region[ty1:ty1 + 4 * (ty1 - ty0) + 40, tx0 - 4:tx1 + 5] = True
    wc = max(components(white & region, 100), key=len)
    wx0, wx1, wy0, wy1 = wc[:, 1].min(), wc[:, 1].max(), wc[:, 0].min(), wc[:, 0].max()
    return [round((wx0 + wx1) / 2, 1), round((wy0 + wy1) / 2, 1), int(wx1 - wx0 + 1), int(wy1 - wy0 + 1), 0.0, int(ty1 - ty0 + 1)]


# ---------------------------------------------------------------- CUT 7: the two of them, full figure, 3/4
official = Image.open(f"{SRC}/official_turnaround.jpg").convert("RGB")
citizen = Image.open(f"{SRC}/citizen_turnaround.png").convert("RGB")
# the official's card face is white and enclosed: no 'loose' keying for him (it would take enclosed paper-white out)
off = trim_floor(only_figure(upscale(key_cell(official, (840, 50, 1080, 760), seeds=("top", "left", "right", "bottom"), loose=False))))
cz = trim_floor(only_figure(upscale(key_cell(citizen, (560, 70, 830, 705), seeds=("top", "left", "right", "bottom"), loose=True))))[:, ::-1].copy()
for name, arr in (("official_side", off), ("cz_34_full", cz)):
    eyes = find_eyes(arr)
    arr2, skin = clean_eyes(arr, eyes)
    Image.fromarray(arr2, "RGBA").save(f"{OUT}/v10_{name}.png", optimize=True)
    f, bbox = feet(arr2)
    meta[name] = {"size": [arr2.shape[1], arr2.shape[0]], "feet": f, "bbox": bbox, "eyes": eyes, "skin": skin}

# ---------------------------------------------------------------- CUT 6: his 3/4 face without the halo, for blinks
Q34_EYES = [[667.4, 369.9, 32, 67], [815.3, 370.0, 28, 66]]       # CZ.q34.eyes on the page (both pictures share them)
for src, name in ((f"{V4}/v4_cz_34_neutral.png", "cz_34_neutral"), (f"{V8}/v8_cz_34_talk.png", "cz_34_talk")):
    arr = np.asarray(Image.open(src).convert("RGBA")).copy()
    arr2, skin = clean_eyes(arr, Q34_EYES)
    Image.fromarray(arr2, "RGBA").save(f"{OUT}/v10_{name}.png", optimize=True)
    meta[name] = {"eyes": Q34_EYES, "skin": skin}
json.dump(meta, open(f"{OUT}/v10_meta.json", "w"), indent=1)
print("ok", json.dumps(meta))
