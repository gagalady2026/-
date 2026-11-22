"""Backgrounds, back views and village lights for CUT 1, 7 and 8 of the 36-second animatic (assets_v5).

usage: python3 tools/v5_prep.py SRC OUT
  SRC  bg_stairs.png      stairway alley by the sea (CUT 1)            1672x941
       bg_gate_dusk.png   the jade gate from the alley at sunset (CUT 7)
       village_off.png    hillside village at sunset, lights off (CUT 8)
       village_on.png     the same picture with windows and lamps lit
       climb_a.png, climb_b.png   climbing the stairs, back view (two phases of a step), transparent
       walk_away.png      walking away at sunset, back view, transparent
  writes OUT/v5_*.jpg|png and OUT/v5_meta.json

Plates are 1.06x the frame (2035x1144) so the page's camera can move. For CUT 8 the lit picture is split in two:
  v5_village_dark.jpg   the lit picture with every light put out (the sunset picture, darkened to match around it)
  v5_light_NN.png       the lights, grouped by when they come on: street lamps and ground first, then windows up the hill
"""
import json, sys
from collections import deque
import numpy as np
from PIL import Image, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
W, H = 2035, 1144
INK = np.array([38, 33, 31], np.float32)
meta = {}


def plate(name, out, sharpen=True):
    im = Image.open(f"{SRC}/{name}").convert("RGB").resize((W, H), Image.LANCZOS)
    if sharpen:
        im = im.filter(ImageFilter.UnsharpMask(radius=2.0, percent=50, threshold=2))
    im.save(f"{OUT}/{out}", quality=90, optimize=True)
    return np.asarray(im).astype(np.float32)


def clean(name, out):
    """GPT cut-outs: interior alpha ~253 and a faint matting halo. Opaque interior, ink-coloured soft silhouette."""
    a = np.asarray(Image.open(f"{SRC}/{name}").convert("RGBA")).astype(np.float32)
    al = np.clip((a[..., 3] - 16) / (232 - 16), 0, 1)
    rgb = a[..., :3].copy()
    rgb[al < 0.98] = INK
    Image.fromarray(np.dstack([rgb, al * 255]).astype(np.uint8), "RGBA").save(f"{OUT}/{out}", optimize=True)
    ys, xs = np.nonzero(al > 0.5)
    meta[out] = {"size": [a.shape[1], a.shape[0]], "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                 "feet": [round(float(xs[ys > ys.max() - 40].mean()), 1), int(ys.max())]}


def components(mask, min_area=1):
    Hh, Ww = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)]); seen[y0, x0] = True; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < Hh and 0 <= nx < Ww and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
        if len(pts) >= min_area:
            out.append(np.array(pts))
    return out


plate("bg_stairs.png", "v5_stairs.jpg")
plate("bg_gate_dusk.png", "v5_gate_dusk.jpg")
off = plate("village_off.png", "v5_village_off.jpg")
on = plate("village_on.png", "v5_village_on.jpg")
for n in ("climb_a", "climb_b", "walk_away"):
    clean(f"{n}.png", f"v5_{n}.png")

# ---------------------------------------------------------------- the village lights
lum = lambda a: a @ np.array([0.299, 0.587, 0.114], np.float32)
L = lambda m: Image.fromarray((m * 255).astype(np.uint8), "L")
grow = lambda m, n: np.asarray(L(m).filter(ImageFilter.MaxFilter(n))) > 0
opened = lambda m: np.asarray(L(m).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))) > 0   # drops 1-2 px edge lines
gain = lum(on) - lum(off)
core = opened(gain > 22)                  # the lamps and lit windows themselves
ext = grow(opened(gain > 9), 5)           # with their glow and the pools of light they throw
soft = np.asarray(L(grow(ext, 3)).filter(ImageFilter.GaussianBlur(4))).astype(np.float32) / 255
# the lit picture with the lights put out: inside the lights, the sunset picture darkened by the ratio found around them
ratio = (lum(on) + 4) / (lum(off) + 4)
def fblur(a, r):               # float box blur (3 passes ~ Gaussian), edges clamped
    a = a.astype(np.float32)
    for _ in range(3):
        for ax in (0, 1):
            n = a.shape[ax]
            pad = np.concatenate([np.repeat(a.take([0], ax), r + 1, ax), a, np.repeat(a.take([n - 1], ax), r, ax)], ax)
            c = np.cumsum(pad, ax, dtype=np.float64)
            a = ((c.take(range(2 * r + 1, n + 2 * r + 1), ax) - c.take(range(0, n), ax)) / (2 * r + 1)).astype(np.float32)
    return a
# fill the ratio inside the lights from the pixels around them: fine where there are neighbours, coarser in big lit areas
# (a whole lit window), and the picture-wide ratio where nothing is near
wgt = (~grow(ext, 21)).astype(np.float32)
rmed = float(np.median(ratio[wgt > 0]))
fill = lambda r: (fblur(ratio * wgt, r) / np.maximum(fblur(wgt, r), 1e-6), fblur(wgt, r))
R1, k1 = fill(9); R2, k2 = fill(40)
t2 = np.clip(k2 / 0.05, 0, 1); R2 = t2 * R2 + (1 - t2) * rmed
t1 = np.clip(k1 / 0.15, 0, 1); R = np.clip(t1 * R1 + (1 - t1) * R2, 0.3, 1.2)
print("picture-wide on/off ratio", round(rmed, 3))
dark = on * (1 - soft[..., None]) + np.clip(off * R[..., None], 0, 255) * soft[..., None]
Image.fromarray(dark.astype(np.uint8)).save(f"{OUT}/v5_village_dark.jpg", quality=90, optimize=True)
# group the lights: lamps, their pools on the ground, and the street lamp on the pole first; then windows, from the bottom of
# the hill to the top, with a fixed jitter so they come on one by one rather than in rows
lights = []
for c in components(grow(core, 9), 120):
    cy, cx = float(c[:, 0].mean()), float(c[:, 1].mean())
    y_1672 = cy * 941 / H
    pole = abs(cx * 1672 / W - 535) < 40 and abs(y_1672 - 395) < 40
    early = pole or y_1672 > 600
    h = ((int(cx) * 73856093) ^ (int(cy) * 19349663)) % 1000 / 1000
    key = (0.0 if early else 1.0) + (1 - y_1672 / 941) * 0.75 + 0.25 * h
    lights.append((key, early, c))
lights.sort(key=lambda t: t[0])
n_early = sum(1 for t in lights if t[1])
NG_EARLY, NG_LATE = 3, 9
gid = np.zeros((H, W), np.uint8)              # group number + 1 of every lit pixel
for i, (key, early, c) in enumerate(lights):
    if early:
        g = min(NG_EARLY - 1, int(i / max(1, n_early) * NG_EARLY))
    else:
        g = NG_EARLY + min(NG_LATE - 1, int((i - n_early) / max(1, len(lights) - n_early) * NG_LATE))
    gid[c[:, 0], c[:, 1]] = g + 1
# each glow joins the group of the light it surrounds: grow the group numbers out over the soft mask, step by step
reach = soft > 0.004
for _ in range(40):
    d = np.asarray(Image.fromarray(gid, "L").filter(ImageFilter.MaxFilter(3)))
    fill = (gid == 0) & reach & (d > 0)
    if not fill.any():
        break
    gid[fill] = d[fill]
gid[(gid == 0) & reach] = NG_EARLY + NG_LATE      # anything left over comes on with the last windows
meta["lights"] = []
for g in range(NG_EARLY + NG_LATE):
    gm = soft * (gid == g + 1)
    if gm.max() <= 0:
        continue
    ys, xs = np.nonzero(gm > 0.004)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    layer = np.dstack([on[y0:y1, x0:x1], gm[y0:y1, x0:x1, None] * 255]).astype(np.uint8)
    layer[layer[..., 3] == 0] = 0                 # no colour where nothing shows: keeps the PNG small
    Image.fromarray(layer, "RGBA").save(f"{OUT}/v5_light_{g:02d}.png", optimize=True)
    meta["lights"].append({"file": f"v5_light_{g:02d}.png", "at": [x0, y0], "early": g < NG_EARLY})
print("lights:", len(lights), "early:", n_early, "layers:", len(meta["lights"]))
json.dump(meta, open(f"{OUT}/v5_meta.json", "w"), indent=1)
print("ok", meta.get("v5_climb_a.png"), meta.get("v5_climb_b.png"), meta.get("v5_walk_away.png"))
