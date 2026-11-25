"""The Donghae City symbol on a transparent background, from the official CI file on white (assets_ci).

usage: python3 -I tools/ci_key.py CI.png OUT_DIR
  CI.png   the official CI as given (the symbol — a red sun over a blue sea — and 동해시 under it, on white)
  writes
  OUT_DIR/donghae_ci_symbol.png   the symbol alone (sun and sea, without the 동해시 lettering), on a transparent background,
                                  cropped close with 4 px round it. The CI is drawn in three flat colours on white, so each
                                  pixel is read as one of them laid over white at some opacity: the colour that explains it
                                  best is kept as it is in the file (the median of its solid pixels: nothing redrawn or
                                  recoloured) and the opacity becomes its alpha. Faint JPEG noise (alpha < 4%) is cleared
  OUT_DIR/donghae_ci_symbol.json  the colours, the symbol's box in CI.png, its size

When the city's original (AI/PDF) file is available, export the symbol from it with a transparent background instead
(e.g. pdftocairo -png -transp -r 600) and save it under the same name: the page uses whatever is there.
"""
import json, sys
import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
a = np.asarray(Image.open(SRC).convert("RGB")).astype(np.float32)
Wt = np.array([255.0, 255.0, 255.0])
r, g, b = a[..., 0], a[..., 1], a[..., 2]
solid = {"red": (r > 180) & (g < 80) & (b < 80), "blue": (b > 140) & (b - r > 80) & (g < 160), "black": a.max(-1) < 60}
cols = {k: np.median(a[m], axis=0) for k, m in solid.items()}
best_a = np.zeros(a.shape[:2], np.float32); best_e = np.full(a.shape[:2], 1e9, np.float32); best_k = np.zeros(a.shape[:2], np.int8)
for i, (k, f) in enumerate(cols.items()):
    d = Wt - f
    al = np.clip(((Wt - a) * d).sum(-1) / (d * d).sum(), 0, 1)
    e = np.linalg.norm(a - (Wt - al[..., None] * d), axis=-1)
    take = e < best_e
    best_e[take], best_a[take], best_k[take] = e[take], al[take], i
best_a[best_a < 0.04] = 0
names = list(cols)
sym = (best_a > 0) & np.isin(best_k, [names.index("red"), names.index("blue")])
ys, xs = np.nonzero(sym & (best_a > 0.5))
# the lettering sits under the sea's arc with a white gap: the symbol is everything above the first empty band of rows
rows = np.nonzero((best_a * (best_k == names.index("black"))).max(1) > 0.5)[0]
y_text = int(rows.min()) if len(rows) else a.shape[0]
y0, y1 = int(ys.min()), int(min(ys.max(), y_text - 1))
x0, x1 = int(xs.min()), int(xs.max())
m = 4
box = (max(0, x0 - m), max(0, y0 - m), min(a.shape[1], x1 + m + 1), min(y_text - 1, y1 + m + 1))
out = np.zeros(a.shape[:2] + (4,), np.float32)
for i, k in enumerate(names):
    sel = best_k == i
    out[sel, :3] = cols[k]
out[..., 3] = best_a * 255 * (best_k != names.index("black"))
crop = out[box[1]:box[3], box[0]:box[2]]
Image.fromarray(np.clip(crop + 0.5, 0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/donghae_ci_symbol.png", optimize=True)
meta = {"colours": {k: [int(v) for v in c] for k, c in cols.items()}, "box_in_ci": list(box), "size": [box[2] - box[0], box[3] - box[1]],
        "lettering_top": y_text}
json.dump(meta, open(f"{OUT}/donghae_ci_symbol.json", "w"), indent=1)
print(json.dumps(meta))
