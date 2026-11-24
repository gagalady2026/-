"""The closing two-shot's figures lit by the sunset (assets_v11).

usage: python3 tools/v11_prep.py ASSETS_V10 OUT
  ASSETS_V10  v10_official_side.png, v10_cz_34_full.png (made by tools/v10_prep.py)
  writes
  OUT/v11_official_side_dusk.png, OUT/v11_cz_34_full_dusk.png
      the same pictures (same size, same feet and eyes) lit as the plate is: the sun is low on the left, over the sea, so
      - a warm rim of light runs just inside the outline of every edge that faces it (the left edges, and the tops at half
        strength), a band from 5 to ~26 px in from the edge: the ink outline itself stays dark, black hair and the black
        shirt take a warm brown sheen, skin and cloth a warmer, lighter band ("screen" with a sunset orange);
      - the edges turned away from it (the right edges) fall into a soft lavender shade over ~44 px ("multiply"), the
        colour of the shadows on the plate's walls and ground.
      Their turnaround-sheet flat colours otherwise stay as drawn. The skin round each eye is kept as it was (the lids the
      page paints over the eyes use that colour), which the script checks.
  OUT/v11_meta.json  the skin colour round each eye before and after (they must match)
"""
import json, os, sys
import numpy as np
from PIL import Image

V10, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
RIM = np.array([255, 178, 104], np.float32) / 255      # the low sun
SHADE = np.array([206, 190, 226], np.float32) / 255    # the plate's shadow tint (shadow / lit ground ≈ 0.81, 0.75, 0.89)
EYES = {"official_side": [[227.1, 381.9, 19, 54]], "cz_34_full": [[456.4, 317.9, 26, 52], [576.3, 318.4, 22, 51]]}


def runs(solid, axis):
    """For each solid pixel, how far it is from the empty pixel before it along an axis (left → right, or top → bottom),
    and from the one after it."""
    a = solid if axis == 1 else solid.T
    h, w = a.shape
    fwd = np.zeros((h, w), np.float32); back = np.zeros((h, w), np.float32)
    for x in range(w):
        fwd[:, x] = np.where(a[:, x], (fwd[:, x - 1] if x else 0) + 1, 0)
    for x in range(w - 1, -1, -1):
        back[:, x] = np.where(a[:, x], (back[:, x + 1] if x < w - 1 else 0) + 1, 0)
    return (fwd, back) if axis == 1 else (fwd.T, back.T)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def eye_skin(rgb, a, eyes):
    out = []
    for x, y, w, h in eyes:
        r = int(h * 0.9) + 14
        yy, xx = np.mgrid[int(y - r):int(y + r), int(x - r):int(x + r)]
        ring = ((xx - x) ** 2 + (yy - y) ** 2 > (h * 0.8) ** 2) & ((xx - x) ** 2 + (yy - y) ** 2 < r ** 2)
        px = rgb[yy[ring], xx[ring]]
        keep = (a[yy[ring], xx[ring]] > 250) & (px.sum(-1) > 600)
        out.append([round(float(v), 1) for v in np.median(px[keep], axis=0)])
    return out


meta = {}
for name in ("official_side", "cz_34_full"):
    im = np.asarray(Image.open(f"{V10}/v10_{name}.png").convert("RGBA")).astype(np.float32)
    rgb, a = im[..., :3] / 255, im[..., 3]
    solid = a > 128
    left, right = runs(solid, 1)          # distance from the empty pixel to the left (the sun's side) / to the right
    top, _ = runs(solid, 0)               # … and from the one above
    band = lambda d: smooth(4.5, 8, d) * (1 - smooth(13, 26, d))     # just inside the outline, fading in ~20 px
    rim = np.maximum(band(left), 0.5 * band(top)) * 0.5
    shade = (1 - smooth(5, 44, right)) * 0.6
    lit = 1 - (1 - rgb) * (1 - rim[..., None] * RIM)                  # screen
    lit = lit * (1 - shade[..., None] * (1 - SHADE))                  # multiply toward the shade tint
    out = np.dstack([np.clip(lit * 255 + 0.5, 0, 255), im[..., 3:4]]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(f"{OUT}/v11_{name}_dusk.png", optimize=True)
    before, after = eye_skin(im[..., :3], a, EYES[name]), eye_skin(out[..., :3].astype(np.float32), a, EYES[name])
    meta[name] = {"eye_skin_before": before, "eye_skin_after": after,
                  "rim_px": int((rim > 0.05).sum()), "shade_px": int((shade > 0.05).sum())}
    for b, c in zip(before, after):
        assert max(abs(p - q) for p, q in zip(b, c)) <= 2, (name, b, c)
json.dump(meta, open(f"{OUT}/v11_meta.json", "w"), indent=1)
print("ok", json.dumps(meta))
