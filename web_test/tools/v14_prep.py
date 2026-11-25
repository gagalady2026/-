"""The user's new GPT pictures for CUT 4 and CUT 7 (assets_v14).

usage: python3 -I tools/v14_prep.py BENCH.webp FACE.webp BOW.webp OUT
  BENCH.webp  CUT 4: the two of them sitting on a bench, turned to each other (1536x1024, transparent)
  FACE.webp   CUT 7 ①: at the gate at sunset, standing face to face (1254x1254, transparent)
  BOW.webp    CUT 7 ②: the same picture with the official bowing and the citizen raising a hand to see him off
  writes
  OUT/v14_bench_pair.png, OUT/v14_c7_face.png, OUT/v14_c7_bow.png
      the pictures as they are drawn, with their transparency cleaned: the generator left a faint dark haze round the figures
      (alpha 1-24, ~1-7% of the picture) and figures that are 1-4% see-through (alpha 246-254, lossy alpha). The haze is
      cleared, the near-opaque made opaque, specks under 1500 px dropped; edges (alpha 25-245) are kept as drawn.
      The two CUT 7 pictures are drawn small on screen (full figures), so their ink lines read about half as thick as the rest
      of the film: their dark lines (luminance < 95: outlines, eyes, mouths; not the lighter wrinkle and fold strokes) are
      thickened 2 px a side, worked at twice the size so the new edges stay soft
  OUT/v14_meta.json  sizes; eyes [x, y, w, h] and the skin round them (for blinks); the figures' feet and heights
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image, ImageFilter

BENCH, FACE, BOW, OUT = sys.argv[1:5]
os.makedirs(OUT, exist_ok=True)


def keep_big(solid, min_px):
    """The 4-connected parts of `solid` of at least min_px pixels."""
    h, w = solid.shape
    seen = np.zeros_like(solid); keep = np.zeros_like(solid)
    for y0, x0 in zip(*np.nonzero(solid)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)]); seen[y0, x0] = True; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and solid[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True; q.append((yy, xx))
        if len(pts) >= min_px:
            ys, xs = zip(*pts); keep[list(ys), list(xs)] = True
    return keep


def clean(src, dst):
    a = np.asarray(Image.open(src).convert("RGBA")).astype(np.int32)
    al = a[..., 3]
    al = np.where(al <= 24, 0, np.where(al >= 246, 255, al))
    al = np.where(keep_big(al > 0, 1500), al, 0)
    a[..., 3] = al
    Image.fromarray(a.astype(np.uint8), "RGBA").save(dst, optimize=True)
    return a


def thicken(path, grow, Lmax=95):
    """The picture's dark ink lines grown by `grow` px a side (at 2x: dilate the ink, fill the new ring with the darkest ink
    colour round it, make it opaque; then back down to 1x, premultiplied)."""
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    a = np.asarray(img.resize((w * 2, h * 2), Image.LANCZOS)).astype(np.float32)
    rgb, al = a[..., :3].copy(), a[..., 3].copy()
    ink = (rgb @ np.array([0.299, 0.587, 0.114]) < Lmax) & (al > 100)
    k = int(round(4 * grow)) | 1
    ring = (np.asarray(Image.fromarray((ink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(k))) > 0) & ~ink
    src = rgb.copy(); src[~ink] = 255
    mn = np.dstack([np.asarray(Image.fromarray(src[..., i].astype(np.uint8)).filter(ImageFilter.MinFilter(k))) for i in range(3)])
    rgb[ring] = mn[ring]; al[ring] = 255
    pre = Image.fromarray(np.clip(np.dstack([rgb * al[..., None] / 255, al]), 0, 255).astype(np.uint8), "RGBA").resize((w, h), Image.LANCZOS)
    o = np.asarray(pre).astype(np.float32)
    rgb2 = np.where(o[..., 3:4] > 0, o[..., :3] * 255 / np.maximum(o[..., 3:4], 1), 0)
    Image.fromarray(np.clip(np.dstack([rgb2, o[..., 3]]) + 0.5, 0, 255).astype(np.uint8), "RGBA").save(path, optimize=True)


def skin_round(a, ex, ey, h):
    r = int(h * 0.9) + 12
    yy, xx = np.mgrid[int(ey - r):int(ey + r), int(ex - r):int(ex + r)]
    ring = ((xx - ex) ** 2 + (yy - ey) ** 2 > (h * 0.8) ** 2) & ((xx - ex) ** 2 + (yy - ey) ** 2 < r ** 2)
    px = a[yy[ring], xx[ring]]
    keep = (px[:, 3] > 250) & (px[:, :3].sum(-1) > 600)
    return [int(v) for v in np.median(px[keep][:, :3], axis=0)]


def extent(a, x0, x1):
    al = a[:, x0:x1, 3] > 128
    ys, xs = np.nonzero(al)
    bottom = ys.max()
    feet = np.nonzero(al[bottom - 40:bottom + 1].any(0))[0] + x0
    return {"x": [int(xs.min() + x0), int(xs.max() + x0)], "top": int(ys.min()), "bottom": int(bottom),
            "feet_x": [int(feet.min()), int(feet.max())]}


meta = {}
b = clean(BENCH, f"{OUT}/v14_bench_pair.png")
f = clean(FACE, f"{OUT}/v14_c7_face.png")
w = clean(BOW, f"{OUT}/v14_c7_bow.png")
# eyes, measured on the pictures (the dark ovals; the citizen's left eye in CUT 4 joins his worried lid line, so it is set by hand)
EYES = {"bench_cz": [[553.5, 285.0, 18, 27], [625.0, 263.5, 17, 32]], "bench_off": [[893.5, 267.0, 14, 33], [963.0, 282.0, 17, 33]],
        "c7_cz": [[400.0, 292.5, 17, 34], [461.0, 282.0, 13, 31]], "c7_off": [[813.0, 259.0, 13, 35]]}
for k, src in (("bench_cz", b), ("bench_off", b), ("c7_cz", f), ("c7_off", f)):
    meta[k] = {"eyes": EYES[k], "skin": skin_round(src, EYES[k][0][0], EYES[k][0][1], EYES[k][0][3])}
meta["bench"] = {"size": [int(b.shape[1]), int(b.shape[0])], "extent": extent(b, 0, b.shape[1])}
meta["c7"] = {"size": [int(f.shape[1]), int(f.shape[0])], "split_x": 620,
              "face": {"cz": extent(f, 0, 620), "off": extent(f, 620, f.shape[1])},
              "bow": {"cz": extent(w, 0, 620), "off": extent(w, 620, w.shape[1])}}
for name in ("v14_c7_face.png", "v14_c7_bow.png"):
    thicken(f"{OUT}/{name}", 2.0)
meta["c7"]["lines_thickened_px"] = 2.0
json.dump(meta, open(f"{OUT}/v14_meta.json", "w"), indent=1)
print(json.dumps(meta))
