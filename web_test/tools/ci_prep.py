"""The Donghae City logo for the end card, taken from the flag picture the user sent (assets_ci).

usage: python3 tools/ci_prep.py FLAG.png OUT
  FLAG.png  a picture of the city flag (the symbol — a red sun rising over a blue sea line — and the name 동해시, on white)
  writes
  OUT/donghae_logo.png   the symbol and the name cut from the flag exactly as they are (no redrawing, no recolouring): the
                         box round the coloured and black parts, with a margin of white; near-white flag cloth (min
                         channel >= 244) is set to pure white so it meets the end card's white plate without a seam
  OUT/ci_meta.json       the crop box in the flag picture, the logo's size, its colours as sampled

This is a stand-in until the official CI file arrives (the design doc: the CI is the city's own file, never drawn). To use the
official file, save it as OUT/donghae_logo.png (a horizontal or vertical lock-up on white or transparent): the page fits
whatever is there into the same plate.
"""
import json, os, sys
import numpy as np
from PIL import Image

SRC, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
a = np.asarray(Image.open(SRC).convert("RGB")).astype(int)
h, w = a.shape[:2]
r, g, b = a[..., 0], a[..., 1], a[..., 2]
ink = (a.min(-1) < 200)                                          # anything clearly not white cloth
# the flag's own frame (its outline, the grommets) and the shop's banner above it are not part of the logo: keep only the
# large coloured parts in the middle of the cloth
inside = np.zeros_like(ink)
inside[int(0.40 * h):int(0.80 * h), int(0.28 * w):int(0.78 * w)] = True
ys, xs = np.nonzero(ink & inside)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
m = int(0.06 * max(x1 - x0, y1 - y0))                             # a little white round it
box = [int(x0 - m), int(y0 - m), int(x1 + m + 1), int(y1 + m + 1)]
crop = a[box[1]:box[3], box[0]:box[2]].copy()
crop[crop.min(-1) >= 244] = 255
Image.fromarray(crop.astype(np.uint8), "RGB").save(f"{OUT}/donghae_logo.png", optimize=True)
red = (r > 170) & (g < 90) & (b < 90) & inside
blue = (b > 140) & (b - r > 60) & inside
meta = {"source_size": [w, h], "crop_box": box, "logo_size": [box[2] - box[0], box[3] - box[1]],
        "red": [int(v) for v in np.median(a[red], axis=0)], "blue": [int(v) for v in np.median(a[blue], axis=0)]}
json.dump(meta, open(f"{OUT}/ci_meta.json", "w"), indent=1)
print("ok", json.dumps(meta))
