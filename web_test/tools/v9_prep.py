"""Clean eyes for the citizen's front view (assets_v9).

usage: python3 tools/v9_prep.py ASSETS_V4 OUT
  ASSETS_V4  v4_cz_front.png (made by tools/v4_prep.py)
  writes
  OUT/v9_cz_front.png  CUT 7b: the same picture without the light halo the 3x upscale's sharpening left round each pupil.
                       When he shuts his eyes in his bow, the page paints a skin-coloured lid over each eye; with the halo
                       there, a pale ring showed round the closed eyes. The halo is filled with the skin round it (diffused
                       inward) and each pupil keeps a soft edge.
  prints the skin colour round each eye, for the lid (CZ.front.skin on the page)
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageFilter

V4, OUT = sys.argv[1], sys.argv[2]
EYES = [(321.7, 315.0), (460.3, 314.8)]                 # the eyes as the page measures them (CZ.front.eyes)
im = np.asarray(Image.open(f"{V4}/v4_cz_front.png").convert("RGBA")).copy()
meta = {"eyes": []}
for EX, EY in EYES:
    x0, y0 = int(EX - 40), int(EY - 60)
    win = im[y0:y0 + 120, x0:x0 + 80].astype(np.float32)
    lum = win[..., :3].sum(-1)
    core = lum < 330                                     # the pupil and its dark edge
    near = np.asarray(Image.fromarray((core * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(17))) > 0
    ring = near & ~core
    rim = np.asarray(Image.fromarray((near * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(7))) > 0
    skin = np.median(win[rim & ~near][:, :3], axis=0)    # the skin just outside the halo
    F = win[..., :3].copy()
    F[near] = skin
    for _ in range(600):
        avg = (np.roll(F, 1, 0) + np.roll(F, -1, 0) + np.roll(F, 1, 1) + np.roll(F, -1, 1)) / 4
        F[near] = avg[near]
    wgt = np.clip((620 - lum) / 470, 0, 1)               # how much of each pixel is pupil (its antialiased edge partly)
    wgt[~near] = 0
    wgt = wgt[..., None]
    pupil = np.where(core[..., None], win[..., :3], np.array([22, 16, 16], np.float32))
    im[y0:y0 + 120, x0:x0 + 80, :3] = np.clip(wgt * pupil + (1 - wgt) * F, 0, 255).astype(np.uint8)
    meta["eyes"].append({"at": [EX, EY], "skin": [int(v) for v in skin], "halo_px": int(ring.sum())})
os.makedirs(OUT, exist_ok=True)
Image.fromarray(im, "RGBA").save(f"{OUT}/v9_cz_front.png", optimize=True)
json.dump(meta, open(f"{OUT}/v9_meta.json", "w"), indent=1)
print("ok", meta)
